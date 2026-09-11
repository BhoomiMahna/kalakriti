from artisan_ai.translation.indictrans import IndicTransProvider

translator = IndicTransProvider()

tests = {
    "hi": "यह हाथ से बनाया हुआ उत्पाद है।",
    "pa": "ਇਹ ਹੱਥ ਨਾਲ ਬਣਾਇਆ ਹੋਇਆ ਉਤਪਾਦ ਹੈ।",
    "ta": "இது கையால் செய்யப்பட்ட ஒரு பொருள்.",
    "te": "ఇది చేతితో తయారు చేసిన ఉత్పత్తి.",
    "bn": "এটি হাতে তৈরি একটি পণ্য।",
    "mr": "हे हाताने बनवलेले उत्पादन आहे.",
    "gu": "આ હાથથી બનાવેલ ઉત્પાદન છે.",
    "kn": "ಇದು ಕೈಯಿಂದ ತಯಾರಿಸಿದ ಉತ್ಪನ್ನವಾಗಿದೆ.",
    "ml": "ഇത് കൈകൊണ്ട് നിർമ്മിച്ച ഉൽപ്പന്നമാണ്.",
    "or": "ଏହା ହାତରେ ତିଆରି ହୋଇଥିବା ଉତ୍ପାଦ।",
}

for language, text in tests.items():
    print("\n" + "=" * 60)
    print(f"Language: {language}")
    print(f"Input: {text}")

    try:
        result = translator.translate(
            text=text,
            source_language=language,
            target_language="en",
        )

        print(f"English: {result.translated_text}")

    except Exception as e:
        print(f"ERROR: {e}")

