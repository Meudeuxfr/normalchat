import os
import re
from transformers import GPT2Tokenizer, GPT2LMHeadModel, Trainer, TrainingArguments, TextDataset, DataCollatorForLanguageModeling

def load_and_prepare_data(file_pattern="chat_log_*.txt", output_file="fine_tune_data.txt"):
    import glob
    files = glob.glob(file_pattern)
    with open(output_file, "w", encoding="utf-8") as out_f:
        for file in files:
            with open(file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    # Clean line to remove timestamps and usernames, keep only message text
                    match = re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - (.+?): (.+)", line)
                    if match:
                        user, message = match.groups()
                        # Write message to output file
                        out_f.write(message.strip() + "\n")

def fine_tune_gpt2(train_file="fine_tune_data.txt", model_name="gpt2", output_dir="./fine_tuned_gpt2", epochs=5):
    tokenizer = GPT2Tokenizer.from_pretrained(model_name)
    model = GPT2LMHeadModel.from_pretrained(model_name)

    # Prepare dataset
    train_dataset = TextDataset(
        tokenizer=tokenizer,
        file_path=train_file,
        block_size=128
    )
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, mlm=False,
    )

    training_args = TrainingArguments(
        output_dir=output_dir,
        overwrite_output_dir=True,
        num_train_epochs=epochs,
        per_device_train_batch_size=2,
        save_steps=500,
        save_total_limit=2,
        prediction_loss_only=True,
        logging_dir='./logs',
        logging_steps=100,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=data_collator,
        train_dataset=train_dataset,
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

if __name__ == "__main__":
    print("Preparing data...")
    load_and_prepare_data()
    print("Starting fine-tuning with increased epochs...")
    fine_tune_gpt2()
    print("Fine-tuning completed. Model saved to ./fine_tuned_gpt2")
