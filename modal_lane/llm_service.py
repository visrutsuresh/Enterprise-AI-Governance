import modal  # type:ignore

# Qwen3-30B-A3B abandoned 2026-07-24: its 4-6 min load could never fit a request
# window (cold calls died at every timeout ceiling) and it forced $2/hr 40GB+ cards.
# Same recipe as the sibling project's proven review lane: 14B 4-bit loads in ~60s on a $1/hr A10G.
MODEL = "Qwen/Qwen2.5-14B-Instruct"

# copied from the sibling legal project's proven lane; distinct app name so a
# deploy from THIS repo can never overwrite the sibling's live endpoint
app = modal.App("governance-private-llm")

# the container recipe: Debian + the libraries needed to run the model
# transformers pinned: 4.54+ rewrote model loading and silently skips 4-bit quantization
image = modal.Image.debian_slim(python_version="3.12").pip_install("torch", "transformers==4.53.2", "accelerate", "bitsandbytes", "fastapi[standard]")

# persistent disk: the ~60GB of weights download once, then live here
cache = modal.Volume.from_name("hf-cache", create_if_missing=True)


@app.cls(
    image=image,
    gpu="A10G",  # 14B 4-bit is ~9GB, fits with room for long-context KV
    volumes={"/cache": cache},
    timeout=600,  # ~60s load + one long generation, with slack
    scaledown_window=300,  # 5 warm minutes; re-warming costs ~60s, not 5 min
    max_containers=4,  # one per parallel inspector: the fan-out is only real if the lane can serve it.
    # Was 1, which made every 'parallel' inspector queue behind the one before it. Raising this is a
    # DELIBERATE cost increase (CEO call 2026-08-04): up to 4 GPUs warm at once during an assessment.
    secrets=[modal.Secret.from_name("llm-lane-token")],
)
class LLM:
    @modal.enter()
    def load(self):
        import os

        os.environ["HF_HOME"] = "/cache"
        # quantize-on-load fragments GPU memory badly; without this the A10G OOMs with ~12GB stuck in holes
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        import torch  # type:ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # type:ignore

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL)
        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        self.model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=quant, device_map={"": 0})

    @modal.fastapi_endpoint(method="POST")
    def generate(self, data: dict):
        import os

        if data.get("token") != os.environ["LANE_TOKEN"]:
            from fastapi import HTTPException  # type:ignore

            raise HTTPException(status_code=401, detail="unauthorized")
        prompt = data["prompt"]
        max_new_tokens = data.get("max_new_tokens", 512)

        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(text, return_tensors="pt").to("cuda")
        output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        new_tokens = output[0][inputs.input_ids.shape[1] :]
        reply = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return {"text": reply}
