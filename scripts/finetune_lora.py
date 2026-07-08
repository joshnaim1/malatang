"""Level 2 LoRA fine-tune on verified winning trajectories (SOW section 11.3).

Runs on the MI300X droplet inside the ROCm PyTorch container. Builds the SFT
dataset from accepted trajectories (prompt = bug context, completion = winning
diff + reasoning), then LoRA fine-tunes Qwen2.5-Coder-7B (r=16, alpha=32, target
q/k/v/o projections, 2-3 epochs) via TRL's SFTTrainer, and saves the adapter for
serving through vLLM.

    docker run -it --device=/dev/kfd --device=/dev/dri --group-add video \
      --ipc=host --shm-size 16G rocm/pytorch:latest
    pip install -r requirements-train.txt
    python -m scripts.finetune_lora --output-dir checkpoints/iter-lora --epochs 3

Do NOT run locally — it needs the ROCm torch build and the GPU.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from creator.config import REPO_ROOT
from creator.sft_dataset import MIN_WINS_FOR_LEVEL2, write_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="LoRA fine-tune on verified wins")
    parser.add_argument(
        "--model",
        default=os.environ.get("CREATOR_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct"),
    )
    parser.add_argument("--output-dir", default="checkpoints/iter-lora")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--playbook-version", default="v0")
    parser.add_argument(
        "--dataset",
        default=str(REPO_ROOT / "results" / "sft_wins.jsonl"),
        help="where to write/read the SFT dataset built from trajectories",
    )
    parser.add_argument(
        "--allow-below-min",
        action="store_true",
        help="proceed even with fewer than the SOW minimum verified wins",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    n_wins = write_dataset(dataset_path, playbook_version=args.playbook_version)
    print(f"[finetune] built SFT dataset: {n_wins} verified wins -> {dataset_path}")

    if n_wins < MIN_WINS_FOR_LEVEL2 and not args.allow_below_min:
        print(
            f"STOP: only {n_wins} verified wins (< {MIN_WINS_FOR_LEVEL2}). "
            "SOW section 7 says skip Level 2 below this bar (regression risk). "
            "Re-run with --allow-below-min to override."
        )
        return 2
    if n_wins == 0:
        print("STOP: no verified wins to train on.")
        return 2

    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: training deps not importable (run inside ROCm container): {exc}")
        return 1

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    dataset = load_dataset("json", data_files=str(dataset_path), split="train")

    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )

    sft_config = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=args.learning_rate,
        logging_steps=5,
        bf16=True,
        report_to=[],
        save_strategy="epoch",
        max_seq_length=4096,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset,
        peft_config=lora,
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"[finetune] adapter saved to {args.output_dir}")
    print(
        "[finetune] serve with: vllm serve "
        f"{args.model} --enable-lora --lora-modules iter-lora={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
