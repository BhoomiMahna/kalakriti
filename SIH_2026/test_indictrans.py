import torch

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit.processor import IndicProcessor

MODEL_NAME = "ai4bharat/indictrans2-indic-en-dist-200M"

device = "cuda" if torch.cuda.is_available() else "cpu"

print("Device:", device)
print("Loading model...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True
)

model = AutoModelForSeq2SeqLM.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True
).to(device)

model.eval()

processor = IndicProcessor(inference=True)

text = [
    "ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ। ਇਹ ਹੱਥ ਨਾਲ ਬਣਾਇਆ ਗਿਆ ਹੈ।"
]

processed = processor.preprocess_batch(
    text,
    src_lang="pan_Guru",
    tgt_lang="eng_Latn"
)

inputs = tokenizer(
    processed,
    padding="longest",
    truncation=True,
    return_tensors="pt"
).to(device)

with torch.no_grad():
    generated_tokens = model.generate(
        **inputs,
        max_length=256,
        num_beams=1
    )

decoded = tokenizer.batch_decode(
    generated_tokens,
    skip_special_tokens=True
)

translations = processor.postprocess_batch(
    decoded,
    lang="eng_Latn"
)

print("\nOriginal:")
print(text[0])

print("\nEnglish:")
print(translations[0])

