import os
import sys

sys.path.append(os.path.dirname(__file__))

from gui.app import App


if __name__ == "__main__":
    app = App()
    app.mainloop()
