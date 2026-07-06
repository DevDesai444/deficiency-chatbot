"""
QLoRA fine-tuning for Suggestor and Evaluator adapters.

Designed for Databricks GPU clusters (A10G / A100).
Locally, runs on MPS/CPU with reduced batch size for smoke testing.

Usage:
    # Suggestor adapter
    python notebooks/fine_tune.py --role suggestor --epochs 3

    # Evaluator adapter
    python notebooks/fine_tune.py --role evaluator --epochs 3

    # Quick local smoke test (1 step)
    python notebooks/fine_tune.py --role suggestor --smoke-test

Output:
    data/adapters/{role}/   — LoRA adapter weights
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer

BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
DATA_DIR = Path("data/finetune")
ADAPTER_DIR = Path("data/adapters")

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]

MAX_SEQ_LENGTH = 2048


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--role", choices=["suggestor", "evaluator"], required=True)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--smoke-test", action="store_true", help="Single step for validation")
    p.add_argument("--base-model", default=BASE_MODEL)
    return p.parse_args()


def get_device_config() -> dict:
    if torch.cuda.is_available():
        return {"device": "cuda", "use_4bit": True}
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return {"device": "mps", "use_4bit": False}
    return {"device": "cpu", "use_4bit": False}


def load_model_and_tokenizer(model_name: str, use_4bit: bool):
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if use_4bit:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        model = prepare_model_for_kbit_training(model)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )

    return model, tokenizer


def apply_lora(model) -> None:
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGET_MODULES,
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


_tokenizer_ref = None


def formatting_func(example: dict) -> str:
    return _tokenizer_ref.apply_chat_template(
        example["messages"], tokenize=False, add_generation_prompt=False,
    )


def main() -> None:
    args = parse_args()
    device_cfg = get_device_config()

    print(f"Role: {args.role}")
    print(f"Device: {device_cfg['device']}, 4-bit: {device_cfg['use_4bit']}")

    train_path = DATA_DIR / f"{args.role}_train.jsonl"
    val_path = DATA_DIR / f"{args.role}_val.jsonl"

    if not train_path.exists():
        print(f"Training data not found at {train_path}")
        print("Run: python notebooks/prepare_training_data.py")
        sys.exit(1)

    train_ds = load_dataset("json", data_files=str(train_path), split="train")
    val_ds = load_dataset("json", data_files=str(val_path), split="train") if val_path.exists() else None

    print(f"Train examples: {len(train_ds)}")
    if val_ds:
        print(f"Val examples: {len(val_ds)}")

    model, tokenizer = load_model_and_tokenizer(args.base_model, device_cfg["use_4bit"])
    model = apply_lora(model)

    global _tokenizer_ref
    _tokenizer_ref = tokenizer

    output_dir = ADAPTER_DIR / args.role
    output_dir.mkdir(parents=True, exist_ok=True)

    max_steps = 1 if args.smoke_test else -1
    num_epochs = 1 if args.smoke_test else args.epochs
    batch_size = 1 if args.smoke_test else args.batch_size

    gradient_accumulation = max(1, 16 // batch_size)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=num_epochs,
        max_steps=max_steps,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch" if val_ds else "no",
        bf16=device_cfg["device"] == "cuda",
        fp16=False,
        optim="paged_adamw_8bit" if device_cfg["use_4bit"] else "adamw_torch",
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        formatting_func=formatting_func,
        max_seq_length=MAX_SEQ_LENGTH,
        tokenizer=tokenizer,
        packing=False,
    )

    trainer.train()

    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    print(f"Adapter saved to {output_dir}")

    if val_ds and not args.smoke_test:
        metrics = trainer.evaluate()
        print(f"Eval loss: {metrics.get('eval_loss', 'N/A')}")


if __name__ == "__main__":
    main()
