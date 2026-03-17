from PyQt6.QtWidgets import QMessageBox

def AboutDialog(parent=None):
    """
    提供與舊版相容的介面，顯示關於對話框
    """
    from ChroLens_AutoFlow import VERSION, FULL_APP_NAME
    msg = QMessageBox(parent)
    msg.setWindowTitle(f"關於 {FULL_APP_NAME}")
    msg.setText(f"<b>{FULL_APP_NAME} v{VERSION}</b>")
    msg.setInformativeText(
        "智能影片自動分類與多窗瀏覽工具\n\n"
        "作者: Lucien\n"
        "授權: GPL v3 + Commercial License\n\n"
        "© 2026 ChroLens Studio"
    )
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    return msg
