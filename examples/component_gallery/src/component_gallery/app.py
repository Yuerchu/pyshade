"""应用入口:四个页面覆盖全部组件。"""

from component_gallery.pages import FormPage, OverlaysPage, StructurePage, WidgetsPage
from pyshade.app import ShadeApp

app = ShadeApp(title='PyShade Component Gallery', pages=[WidgetsPage, FormPage, OverlaysPage, StructurePage])
