"""应用入口:编译器和 EventRegistry 共同消费的 ShadeApp。"""

from pyshade.app import ShadeApp
from pyshade.theme import Theme
from settings_panel.pages import SettingsPanelPage

app = ShadeApp(
    title='PyShade Settings Panel Demo',
    pages=[SettingsPanelPage],
    # 主题口子演示:只覆盖 :root token,预编译 style.css 经双层变量机制运行时换肤
    theme=Theme(primary='oklch(0.55 0.18 260)', ring='oklch(0.55 0.18 260)', radius='0.75rem'),
)
