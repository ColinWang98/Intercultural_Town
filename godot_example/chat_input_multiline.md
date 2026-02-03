# 聊天输入框改为多行、自动换行、按范围显示

把聊天 UI 里的 **InputBar** 从 **LineEdit** 换成 **TextEdit**，即可多行输入、按文本框宽度自动换行、在固定范围内显示。

## 场景里要做的

1. 选中原来的 **InputBar** 节点（若是 LineEdit）。
2. 删除该节点，在同一位置新建一个 **TextEdit**，节点名仍为 **InputBar**（或保持脚本里 `$InputBar` 能指向它）。
3. 在 TextEdit 上设置：
   - **Custom Minimum Size**：设一个固定高度（如 60～80），宽度随布局或与原来一致。
   - **Wrap Mode**：选 **Boundary**（`LINE_WRAPPING_BOUNDARY`），文字会按控件宽度换行。
   - **Scroll Fit Content Height** / **Scroll Fit Content Width**：保持**关闭**（false），这样多出的内容会**出现滚动条**，而不是把文本框撑大。
   - 若不需要横向滚动：可关闭 **Horizontal Scroll Bar**，或保持默认。
   - 按需调整 **Placeholder Text**、字体等。

## 脚本已支持

`chat_interface.gd` 已兼容 **LineEdit** 和 **TextEdit**：

- 若 **InputBar** 是 **TextEdit**，会在 `_ready` 里设置 `wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY`，并连接 `gui_input`。
- **Enter** = 发送；**Shift+Enter** = 换行（不发送）。

无需再改脚本，只要把场景里的 InputBar 换成 TextEdit 并按上面设置即可。

---

## 若「聊天记录」区域也没法滚动

**ChatDisplay**（显示历史消息的 RichTextLabel）本身没有滚动条。要让聊天记录可滚动：

1. 在场景里把 **ChatDisplay** 放到 **ScrollContainer** 下面（结构：`ScrollContainer → ChatDisplay`）。
2. 给 ScrollContainer 设好大小（或锚点），让聊天记录区域固定高度；ScrollContainer 会在内容超出时显示滚动条。
3. 脚本里已设置 `chat_display.scroll_following = true`，新消息会尽量跟到底部。
