# AI Product Photo Enhancer

Give it an ordinary product photo — blurry, badly lit, messy background — and it
spits out a clean, professional-looking studio shot.

Under the hood it does four things in a row: sharpens the image, fixes lighting if
it's too dark, cuts out the product, and then uses FLUX to relight it into a proper
studio photo.

---

## First things first — you don't need a model file from me

I know you asked for the model file (a `.pkl` or similar). There isn't one, and
that's actually good news — nothing to download from me or pass around.

The models grab themselves the first time you run the code. This line does it:

```python
pipe = Flux2KleinPipeline.from_pretrained("black-forest-labs/FLUX.2-klein-4B", ...)
```

It quietly downloads FLUX from Hugging Face and keeps it cached on your machine.
The deblur and low-light models do the same. So just run the thing — the downloads
happen by themselves. (First run is slow because of this. After that it's quick.)

---

## What you'll need

You need a **GPU** — the FLUX step won't run on CPU. Free Google Colab is fine, just
switch the runtime to GPU (*Runtime → Change runtime type → GPU*). It wants around
13 GB of VRAM; a T4 works if you keep the output smallish (more on that below).

Installs:

```bash
pip install onnxruntime numpy pillow opencv-python "rembg[gpu]"
pip install --upgrade transformers accelerate
pip install git+https://github.com/huggingface/diffusers.git
```

That last one has to come from GitHub, not the normal pip version — the FLUX pipeline
is too new to be in the released package yet.

---

## Running it

1. Drop your photo in as `/content/blur.jpeg` (or point the `INPUT` path wherever).
2. Run the cells top to bottom.
3. Your result lands at `/content/final.jpg`.

The order it goes in:

1. **Deblur** (NAFNet) → `deblurred.jpg`
2. **Low-light fix** (MIRNet) → `enhanced.jpg` *— but only if the photo is actually dark, otherwise it skips this*
3. **Background removal** (rembg) → `product_isolated.jpg`
4. **Studio relight** (FLUX.2 klein) → `final.jpg`

---

## Plugging it into the backend

The easiest way to use this is to wrap the whole thing in one function:

```python
def enhance_product_photo(input_path, output_path="final.jpg"):
    # deblur -> low-light -> background removal -> FLUX relight
    ...
    result.save(output_path)
    return output_path
```

Then from the API side it's just:

```python
from enhancer import enhance_product_photo
enhance_product_photo("uploads/user_photo.jpg", "outputs/result.jpg")
```

One thing that'll save you pain: **load the models once when the server starts, not
on every request.** FLUX takes a while to load and eats VRAM, so set it up once and
reuse it — otherwise every upload will be painfully slow.

---

## Stuff that'll probably go wrong (and how to fix it)

I hit all of these already, so here's the cheat sheet:

- **"CUDA out of memory"** — the classic. In the FLUX cell, drop `SIZE` down. Try 768,
  then 640, then 512. Smaller = less memory. You can always upscale the final image after.
- **FLUX is crawling on a T4** — change `torch.bfloat16` to `torch.float16` in the FLUX
  cell. Older T4s are happier with fp16.
- **`import rembg` crashes with some numpy error** — versions clashing. Run
  `pip install --force-reinstall "numpy==2.3.2"` and then restart the runtime (the
  restart matters, it won't take effect otherwise).
- **The logo or text on the product looks a bit off in the result** — this is FLUX's
  weak spot; it sometimes nudges branding. Bumping `num_inference_steps` to 6–8 helps.
  For really logo-heavy products, honestly it's safer to skip the FLUX step and just
  drop the cut-out product onto a clean background instead.

---

## Models & licenses

Quick note before we ship anything: check the licenses.

- **FLUX.2 klein 4B** — Apache 2.0, so commercial use is fine. (Heads up: the bigger
  9B version is *non*-commercial, so don't swap that in without checking.)
- **NAFNet**, **MIRNet**, **rembg** — need to confirm each of these from their repos.

Our project brief specifically asks us to document licenses, so let's not skip this.
