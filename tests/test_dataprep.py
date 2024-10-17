import unittest
import base64
from io import BytesIO
from PIL import Image
from transformers import AutoProcessor

from pdelfin.train.dataloader import (
    build_finetuning_dataset,
)

from pdelfin.train.dataprep import (
    prepare_data_for_qwen2_training, build_finetuning_prompt
)
import numpy as np
from tqdm import tqdm
from torch.utils.data import DataLoader
from pdelfin.train.utils import make_dataset
from pdelfin.train.core.config import TrainConfig, DataConfig, SourceConfig

class TestDataprep(unittest.TestCase):
    def testFullDataloader(self):
        processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-7B-Instruct")
        config = TrainConfig(
            train_data=DataConfig(seed=42,
                                  sources=[SourceConfig(name="eval_test",
                                                        target_longest_image_dim=1024,
                                                        target_anchor_text_len=6000,
                                                        response_glob_path="s3://ai2-oe-data/jakep/pdfdata/openai_batch_done_v5_1_eval/*.json")]),

            valid_data=DataConfig(seed=42,
                                  sources=[SourceConfig(name="eval_test",
                                                        target_longest_image_dim=1024,
                                                        target_anchor_text_len=6000,
                                                        response_glob_path="s3://ai2-oe-data/jakep/pdfdata/openai_batch_done_v5_1_eval/*.json")])
        )
        train_dataset, valid_dataset = make_dataset(config, processor)    

        im_end_token_ids = processor.tokenizer("<|im_end|>\n", add_special_tokens=False)["input_ids"]


        #train_dataloader = DataLoader(train_dataset, batch_size=1, num_workers=4, shuffle=False)
        for entry in train_dataset:
            print({x: (y.shape, y.dtype) for (x,y) in entry.items()})

            self.assertEqual(entry["input_ids"].dtype, np.int64)
            self.assertEqual(entry["attention_mask"].dtype, np.int64)
            self.assertEqual(entry["labels"].dtype, np.int64)
            self.assertEqual(entry["pixel_values"].dtype, np.float32)
            self.assertEqual(entry["image_grid_thw"].dtype, np.int64)
            
            # Extract input_ids and labels
            input_ids = entry["input_ids"]
            labels = entry["labels"]

            # 1. Verify that the last token is the end token
            # Ensure input_ids is long enough
            self.assertTrue(len(input_ids) >= len(im_end_token_ids), "Input IDs are shorter than the end token sequence.")

            # Compare the last tokens of input_ids with im_end_token_ids
            self.assertEqual(
                input_ids[-len(im_end_token_ids):].tolist(),
                im_end_token_ids,
                "The last tokens of input_ids do not match the end token sequence."
            )

            # 2. Ensure labels are masked correctly and match input_ids after the mask
            # Find where labels start being non-masked (-100 is the mask value)
            label_indices = np.where(labels != -100)[0]

            # There should be at least one label that is not masked
            self.assertTrue(len(label_indices) > 0, "No unmasked labels found in labels array.")

            first_label_index = label_indices[0]

            # Ensure the masked portion is at least 10 tokens long
            self.assertTrue(first_label_index >= 10, "Masked portion of labels is less than 10 tokens.")

            # Check that all values before first_label_index are -100
            self.assertTrue(
                np.all(labels[:first_label_index] == -100),
                "Labels before the first unmasked token are not all -100."
            )

            # Check that the unmasked labels match the corresponding input_ids
            self.assertTrue(
                np.array_equal(labels[first_label_index:], input_ids[first_label_index:]),
                "Unmasked labels do not match the corresponding input_ids."
            )

            # Optionally, verify that the last unmasked tokens in labels match the end token IDs
            unmasked_labels = labels[labels != -100]
            self.assertEqual(
                unmasked_labels[-len(im_end_token_ids):].tolist(),
                im_end_token_ids,
                "The last unmasked tokens in labels do not match the end token sequence."
            )

  