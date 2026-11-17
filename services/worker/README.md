# Background worker

Celery runs separately from FastAPI, with JSON-only serialization, one process, prefetch one, and execution limits. The generation queue is ready, but no generation task is advertised or enqueued in Step 1. worker.health checks task execution without pretending to generate an image.

providers/base.py defines the image-provider contract. The disabled provider raises explicitly. Local Diffusers and hosted providers must implement the same contract in Step 2 after selecting and benchmarking a model. Do not install PyTorch/Diffusers in the API image. Use a separately pinned CUDA worker image when a measured model is selected.

Benchmark at 512x512, batch one, then measure wall time, peak allocated/reserved VRAM, CPU offload behavior and image quality. Consider FP16, VAE slicing and model CPU offload where supported. Verify the model license and CUDA/PyTorch driver compatibility. The observed GPU has 6144 MiB VRAM; this is hardware inventory, not an inference benchmark.

pipelines/, models/, storage/ and tasks/ reserve module boundaries for later work. They are intentionally empty until needed, not implemented capabilities.
