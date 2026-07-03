import os
import sys

# Ensure project root is on sys.path whether running from source or frozen
_here = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

_arg = sys.argv[1] if len(sys.argv) > 1 else ""

if _arg == '--take-attendance' and len(sys.argv) >= 3:
    # Second instance launched by attendance_page to run the OpenCV camera window
    from take_attendance import take_attendance_session
    take_attendance_session(int(sys.argv[2]))

elif _arg == '--setup-db' and len(sys.argv) >= 3:
    # Called by Inno Setup post-install to initialise MariaDB and write config.ini
    import setup_db
    sys.argv = [sys.argv[0], sys.argv[2]]
    setup_db.main()

elif _arg == '--stop-db':
    # Called by Inno Setup uninstaller to stop the bundled MariaDB server
    from core.mariadb_manager import stop_server
    stop_server()

else:
    from gui.app import App
    app = App()
    app.mainloop()
