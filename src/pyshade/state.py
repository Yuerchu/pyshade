"""双状态模型(design.md §3.3)。

ClientState:可编译,只接受受限表达式子集,编译成前端 JS。
ServerState:任意 Python,走 IPC 回传,由 FastAPI 应用层处理。
"""
