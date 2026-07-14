"""应用入口:编译器和 EventRegistry 共同消费的 ShadeApp。"""

from login_form.pages import LoginPage
from pyshade.app import ShadeApp

app = ShadeApp(title='PyShade Login Demo', pages=[LoginPage])
