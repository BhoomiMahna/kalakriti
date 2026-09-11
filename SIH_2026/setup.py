from setuptools import setup, find_packages

setup(
    name="artisan_ai",
    version="0.1.0",
    description=(
        "Multilingual Voice-to-Product-Description AI Pipeline for Indian Artisans"
    ),
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.10",
    install_requires=[
        "pydantic>=2.5.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "pydub>=0.25.1",
        "librosa>=0.10.1",
        "soundfile>=0.12.1",
        "openai-whisper>=20231117",
        "transformers>=4.40.0",
        "accelerate>=0.27.0",
        "torch>=2.1.0",
        "langdetect>=1.0.9",
        "sentencepiece>=0.1.99",
        "sacremoses>=0.1.1",
        "google-generativeai>=0.7.0",
        "openai>=1.30.0",
    ],
    extras_require={
        "eval": [
            "jiwer>=3.0.3",
            "sacrebleu>=2.4.0",
            "rouge-score>=0.1.2",
        ],
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
