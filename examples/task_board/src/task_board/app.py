"""应用入口:pages[0] 即初始页。"""

from pyshade.app import ShadeApp
from task_board.pages import BoardPage, StatsPage

app = ShadeApp(title='PyShade Task Board Demo', pages=[BoardPage, StatsPage])
