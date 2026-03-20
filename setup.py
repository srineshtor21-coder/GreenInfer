from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="greeninfer",
    version="0.1.0",
    author="Srinesh Toranala",
    description="Green Orchestration Framework for energy-efficient LLM inference",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/srineshtor21-coder/GreenInfer",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "groq>=0.9.0",
        "transformers>=4.40.0",
        "torch>=2.0.0",
        "httpx>=0.27.0",
        "codecarbon>=2.4.0",
    ],
    extras_require={
        "training": [
            "scikit-learn>=1.3.0",
            "numpy>=1.24.0",
            "datasets>=2.18.0",
        ],
        "server": [
            "fastapi>=0.111.0",
            "uvicorn>=0.30.0",
            "pydantic>=2.7.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="green ai llm inference energy efficiency carbon sustainability orchestration",
)
