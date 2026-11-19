BILLOMADFX: MT5 DEMO-ONLY permission checker and helper
=======================================================
1. Open the Valetax MT5 desktop application and log in to your DEMO account.
2. Run RUN_MT5_DEMO_PERMISSIONS.bat. No Administrator access is needed.
3. It checks account type, server, connectivity and terminal permissions.
4. If needed, type ENABLE DEMO to approve toggling the global Algo Trading control via MT5's Ctrl+E shortcut.
5. If the separate external Python API restriction is ON, follow the one-time onscreen instructions in MT5 Options > Expert Advisors. There is no officially documented Python setter for this checkbox.
6. It checks the permissions again and prints READY if all required flags are set.

Never sends an order, never saves or asks for your MT5 password.
Refuses to enable permissions if the active terminal account is REAL or not connected.
The global Algo Trading switch can affect OTHER trading programs on that MT5 terminal; close other Expert Advisors before enabling.
If you switch to a funded account, turn Algo Trading OFF immediately.
If MT5 is installed elsewhere, in PowerShell run:
  .\ENABLE_MT5_DEMO_PERMISSIONS.ps1 -Mt5Path "C:\full\path\terminal64.exe"

This helper has been syntax-checked but cannot be validated against your Windows/Valetax installation from this environment.
