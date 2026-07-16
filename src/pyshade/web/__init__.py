"""web target(M4 最小形态,design.md §3.10):`pyshade serve` 的生产 dispatcher 与编排。"""

from pyshade.web._serve import make_web_asgi, run_serve

__all__ = ['make_web_asgi', 'run_serve']
