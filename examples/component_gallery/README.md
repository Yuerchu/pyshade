# component_gallery

PyShade 组件画廊:四个页面铺开全部 **26 个组件 + Each + 路由**。

首要职责是给 CI 提供"真实 tsc"校验面——生成代码的每种发射形态(受控 useState、
选项 map、asChild 槽、多槽容器、`.map` 模板、`rt.navigate`、const 字面量、编译期
markdown/高亮)都在这里出现一次,`pnpm -C frontend typecheck` 直接对生成产物做类型检查。

| 页面 | 覆盖 |
|------|------|
| WidgetsPage | Heading / Text / Badge / Alert / Separator / Skeleton / Progress(ServerRef)/ Link / Markdown / CodeBlock |
| FormPage | Input / PasswordInput / Textarea / Checkbox / Switch / Select / RadioGroup / Slider |
| OverlaysPage | Dialog(trigger 槽 + 受控 open)/ AlertDialog / Tooltip |
| StructurePage | Tabs / Accordion / ScrollArea / Each(changelog 列表) |

## 运行

```bash
uv run pyshade build component_gallery.app:app --out frontend/src/generated  # PYTHONPATH=examples/component_gallery/src
pnpm -C frontend build
uv --project examples/component_gallery run python -m component_gallery
```
