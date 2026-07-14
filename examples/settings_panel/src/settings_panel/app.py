"""应用入口:编译器和 EventRegistry 共同消费的 ShadeApp。"""

from pyshade.app import ShadeApp
from settings_panel.pages import SettingsPanelPage

app = ShadeApp(title='PyShade Settings Panel Demo', pages=[SettingsPanelPage])
