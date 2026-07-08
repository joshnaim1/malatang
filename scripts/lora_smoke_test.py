"""Build step 4 (SOW section 11.3): LoRA smoke test — go/no-go gate.

Runs ONE LoRA training step on 10 dummy samples inside the ROCm PyTorch
container on the MI300X droplet, before any real Level 2 work. If this fights us
for more than ~half a day, Level 2 is cut (SOW section 11.3 / risk register).

This must run on the droplet, NOT locally:

    docker run -it --device=/dev/kfd --device=/dev/dri --group-add video \
      --ipc=host --shm-size 16G rocm/pytorch:latest
    pip install -r requirements-train.txt
    python -m scripts.lora_smoke_test            # uses CREATOR_MODEL from .env
    python -m scripts.lora_smoke_test --model Qwen/Qwen2.5-Coder-0.5B-Instruct  # fast sanity

Exit code 0 = GO, non-zero = NO-GO. The result is reported either way.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile


def _dummy_samples(n: int) -> list[dict]:
    base = [
        ("Fix the missing await in loadTotal().", "Add `await` before the Promise.all call."),
        ("Guard against null user before reading .name.", "Use optional chaining: user?.name."),
        ("Correct the off-by-one in the slice end index.", "Change end to start + pageSize."),
        ("Close the unterminated JSX </main tag.", "Add the missing `>`: </main>."),
        ("Intl.NumberFormat received cents not dollars.", "Divide by 100 before formatting."),
    ]
    samples = []
    for i in range(n):
        prompt, completion = base[i % len(base)]
        samples.append(
            {
                "messages": [
                    {"role": "system", "content": "You are a terse bug-fixing assistant."},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": completion},
                ]
            }
        )
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description="LoRA smoke test (go/no-go)")
    parser.add_argument(
        "--model",
        default=os.environ.get("CREATOR_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct"),
    )
    parser.add_argument("--num-samples", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=1)
    args = parser.parse_args()

    print(f"[smoke] model: {args.model}")
    print(f"[smoke] samples: {args.num_samples}, max_steps: {args.max_steps}")

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer
    except Exception as exc:  # noqa: BLE001
        print(f"NO-GO: training deps not importable (run inside ROCm container): {exc}")
        return 2

    print(f"[smoke] torch {torch.__version__}, cuda/hip available: {torch.cuda.is_available()}")

    try:
        tokenizer = AutoTokenizer.from_pretrained(args.model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

        dataset = Dataset.from_list(_dummy_samples(args.num_samples))

        lora = LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )

        with tempfile.TemporaryDirectory(prefix="lora_smoke_") as outdir:
            sft_config = SFTConfig(
                output_dir=outdir,
                max_steps=args.max_steps,
                per_device_train_batch_size=1,
                gradient_accumulation_steps=1,
                learning_rate=2e-4,
                logging_steps=1,
                bf16=True,
                report_to=[],
                save_strategy="no",
                max_seq_length=1024,
            )
            trainer = SFTTrainer(
                model=model,
                args=sft_config,
                train_dataset=dataset,
                peft_config=lora,
                processing_class=tokenizer,
            )
            result = trainer.train()

        loss = getattr(result, "training_loss", None)
        print(f"[smoke] training_loss: {loss}")
        if loss is None or math.isnan(loss) or math.isinf(loss):
            print("NO-GO: training step completed but loss is not finite.")
            return 3
    except Exception as exc:  # noqa: BLE001
        print(f"NO-GO: LoRA training step failed: {type(exc).__name__}: {exc}")
        return 1

    print("GO: LoRA fine-tuning path works on this box (1 step, finite loss).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
