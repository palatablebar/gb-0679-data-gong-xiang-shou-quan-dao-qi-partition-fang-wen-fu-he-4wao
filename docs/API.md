# 接口

模块GET使用仓内样例，模块POST可传csv或rows与context，直接计算当前规则。/api/runs使用完整流水线并原子保存。每个阶段返回rows、quarantine、metrics；后续阶段还返回累计隔离。/api/upload接收multipart文件file。/api/runs/<id>/archive只导出一份带清单与证据的CSV，批次引用已退役别名且迁移结果未说明其归属差异时返回409。

/api/retirements：GET列出全部迁移结果；POST传alias与retired_at执行退役，返回唯一迁移结果（同一退役重试幂等，不新增）；/api/retirements/<id>返回单条，不存在返回404。
