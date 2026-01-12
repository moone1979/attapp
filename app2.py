import flet as ft
from datetime import datetime
import zoneinfo
from supabase import create_client

# --- Supabase接続設定 ---
URL = "https://novsbhmrsyurgmjextxg.supabase.co"
KEY = "sb_publishable_Kt4eOMIPaS50FJCb4drWGw_sGcLDWdb"
supabase = create_client(URL, KEY)
JST = zoneinfo.ZoneInfo("Asia/Tokyo")

def main(page: ft.Page):
    page.title = "社内勤怠システム"
    page.window_width = 450
    page.window_height = 800
    page.theme_mode = ft.ThemeMode.LIGHT
    
    state = {"user_id": "", "user_name": ""}

    def show_dashboard():
        page.controls.clear()
        
        page.appbar = ft.AppBar(
            title=ft.Text(f"{state['user_name']} さん"),
            bgcolor="#E1E2E5", 
            actions=[ft.IconButton(ft.Icons.LOGOUT, on_click=lambda _: show_login())]
        )

        def handle_stamp(stamp_type):
            print(f"DEBUG: {stamp_type} 処理開始")
            
            # 処理中通知（0.80.1で最も安定する表示方法）
            sb = ft.SnackBar(ft.Text(f"{stamp_type} 送信中..."))
            page.overlay.append(sb)
            sb.open = True
            page.update()
            
            try:
                now = datetime.now(JST)
                data = {
                    "社員ID": state["user_id"],
                    "氏名": state["user_name"],
                    "日付": now.strftime("%Y-%m-%d"),
                }
                if stamp_type == "in":
                    data["出勤時刻"] = now.strftime("%H:%M")
                else:
                    data["退勤時刻"] = now.strftime("%H:%M")
                
                # Supabase送信
                supabase.table("attendance_log").insert(data).execute()
                print(f"DEBUG: {stamp_type} 送信成功")
                
                # 成功通知を出し直す
                success_sb = ft.SnackBar(
                    content=ft.Text(f"【{stamp_type}】記録完了！ {now.strftime('%H:%M')}"),
                    bgcolor="green"
                )
                page.overlay.append(success_sb)
                success_sb.open = True
                
            except Exception as ex:
                print(f"DEBUG: エラー: {ex}")
                error_sb = ft.SnackBar(content=ft.Text(f"エラー: {ex}"), bgcolor="red")
                page.overlay.append(error_sb)
                error_sb.open = True
            
            page.update()

        page.add(
            ft.Column([
                ft.Container(height=20),
                ft.Text("本日の打刻", size=25, weight="bold"),
                ft.Divider(height=40),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW), ft.Text("出勤打刻", size=20)], alignment="center"),
                    on_click=lambda _: handle_stamp("in"),
                    style=ft.ButtonStyle(bgcolor="orange", color="white"),
                    height=100, width=320,
                ),
                ft.Container(height=20),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.STOP), ft.Text("退勤打刻", size=20)], alignment="center"),
                    on_click=lambda _: handle_stamp("out"),
                    style=ft.ButtonStyle(bgcolor="blue", color="white"),
                    height=100, width=320,
                ),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
        page.update()

    def show_login():
        page.controls.clear()
        page.appbar = None
        id_field = ft.TextField(label="社員ID", value="19671219")
        pw_field = ft.TextField(label="パスワード", password=True, value="19671219")
        
        def login_click(e):
            res = supabase.table("社員ログイン情報").select("*").eq("社員ID", id_field.value).execute()
            if not res.data:
                res = supabase.table("社員ログイン情報").select("*").eq("社員ID", int(id_field.value)).execute()

            if res.data and str(res.data[0].get("パスワード", "")).strip() == pw_field.value:
                state["user_id"] = str(res.data[0].get("社員ID"))
                state["user_name"] = res.data[0].get("氏名")
                show_dashboard()
            else:
                login_err = ft.SnackBar(ft.Text("ログイン失敗"))
                page.overlay.append(login_err)
                login_err.open = True
            page.update()

        page.add(ft.Column([
            ft.Container(height=80),
            ft.Icon(ft.Icons.BUSINESS, size=80, color="blue"),
            ft.Text("勤怠管理システム", size=30, weight="bold"),
            id_field, pw_field,
            ft.FilledButton("ログイン", on_click=login_click, width=300, height=50),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        page.update()

    show_login()

# --- 警告を消し、描画を安定させる最新の起動命令 ---
if __name__ == "__main__":
    ft.run(main)