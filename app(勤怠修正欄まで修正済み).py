import flet as ft
from datetime import datetime
import zoneinfo
import re # 時刻チェック用
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
    
    state = {"user_id": "", "user_name": "", "edit_mode": False}

    def show_dashboard():
        page.controls.clear()
        today = datetime.now(JST).strftime("%Y-%m-%d")
        res = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).eq("日付", today).execute()
        
        in_time = ""
        out_time = ""
        if res.data:
            record = res.data[0]
            in_time = record.get("出勤時刻") or ""
            out_time = record.get("退勤時刻") or ""

        has_in = in_time != ""
        has_out = out_time != ""

        # 手入力用フィールド（スッキリさせるために右側のテキストは削除）
        in_field = ft.TextField(value=in_time, label="出勤(HH:MM)", width=110, text_size=16, dense=True)
        out_field = ft.TextField(value=out_time, label="退勤(HH:MM)", width=110, text_size=16, dense=True)

        # 時刻の形式チェック関数 (00:00 〜 23:59)
        def is_valid_time(t):
            if not t: return True # 空欄はOK
            return bool(re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', t))

        def save_manual(e):
            # 入力チェック
            if not is_valid_time(in_field.value) or not is_valid_time(out_field.value):
                page.snack_bar = ft.SnackBar(ft.Text("時刻は 09:30 のような形式で入力してください"), bgcolor="red")
                page.snack_bar.open = True
                page.update()
                return

            try:
                # 既存データを削除して再挿入
                supabase.table("attendance_log").delete().eq("社員ID", state["user_id"]).eq("日付", today).execute()
                
                final_data = {
                    "社員ID": state["user_id"],
                    "氏名": state["user_name"],
                    "日付": today,
                    "出勤時刻": in_field.value if in_field.value else None,
                    "退勤時刻": out_field.value if out_field.value else None
                }
                supabase.table("attendance_log").insert(final_data).execute()
                
                state["edit_mode"] = False
                show_dashboard()
                page.snack_bar = ft.SnackBar(ft.Text("保存しました"), bgcolor="green")
                page.snack_bar.open = True
            except Exception as ex:
                print(f"DEBUG Error: {ex}")
            page.update()

        def toggle_edit(e):
            state["edit_mode"] = not state["edit_mode"]
            show_dashboard()

        page.appbar = ft.AppBar(title=ft.Text(f"{state['user_name']} さん"), bgcolor="#E1E2E5")

        # カードの中身（「←出勤」などの文字を削除）
        if state["edit_mode"]:
            history_content = ft.Column([
                ft.Container(height=5),
                in_field,
                out_field,
                ft.Row([
                    ft.ElevatedButton("保存", on_click=save_manual, bgcolor="green", color="white"),
                    ft.TextButton("キャンセル", on_click=toggle_edit),
                ], alignment="center", spacing=10)
            ], horizontal_alignment="center", spacing=15)
        else:
            history_content = ft.Column([
                ft.Row([ft.Icon(ft.Icons.LOGIN, color="orange"), ft.Text(f"出勤: {in_time or '--:--'}", size=18)], alignment="center"),
                ft.Row([ft.Icon(ft.Icons.LOGOUT, color="blue"), ft.Text(f"退勤: {out_time or '--:--'}", size=18)], alignment="center"),
            ], spacing=10)

        page.add(
            ft.Column([
                ft.Container(height=10),
                ft.Text("本日の打刻", size=25, weight="bold"),
                ft.Divider(height=20),
                
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW), ft.Text("出勤打刻", size=20)], alignment="center"),
                    on_click=lambda _: handle_stamp("in"),
                    disabled=has_in or state["edit_mode"], 
                    style=ft.ButtonStyle(bgcolor="orange" if not has_in else "grey", color="white"),
                    width=320, height=80,
                ),
                ft.Container(height=10),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.STOP), ft.Text("退勤打刻", size=20)], alignment="center"),
                    on_click=lambda _: handle_stamp("out"),
                    disabled=has_out or state["edit_mode"],
                    style=ft.ButtonStyle(bgcolor="blue" if not has_out else "grey", color="white"),
                    width=320, height=80,
                ),
                
                ft.Divider(height=40),
                
                ft.Row([
                    ft.Text("本日の記録", size=20, weight="bold"),
                    ft.IconButton(
                        icon=ft.Icons.EDIT if not state["edit_mode"] else ft.Icons.CLOSE, 
                        on_click=toggle_edit, 
                        icon_color="blue" if not state["edit_mode"] else "red"
                    )
                ], alignment="center", spacing=20),

                ft.Card(content=ft.Container(content=history_content, padding=20), width=320)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
        page.update()

    # handle_stamp, show_login は前回と同じ
    def handle_stamp(stamp_type):
        today = datetime.now(JST).strftime("%Y-%m-%d")
        now_time = datetime.now(JST).strftime("%H:%M")
        try:
            res = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).eq("日付", today).execute()
            if res.data:
                update_field = "出勤時刻" if stamp_type == "in" else "退勤時刻"
                supabase.table("attendance_log").update({update_field: now_time}).eq("社員ID", state["user_id"]).eq("日付", today).execute()
            else:
                new_data = {"社員ID": state["user_id"], "氏名": state["user_name"], "日付": today, ("出勤時刻" if stamp_type == "in" else "退勤時刻"): now_time}
                supabase.table("attendance_log").insert(new_data).execute()
            show_dashboard()
        except Exception as e:
            print(f"DEBUG Error: {e}")

    def show_login():
        page.controls.clear()
        page.appbar = None
        id_f = ft.TextField(label="社員ID", value="19671219")
        pw_f = ft.TextField(label="パスワード", password=True, value="19671219")
        def login_c(e):
            res = supabase.table("社員ログイン情報").select("*").eq("社員ID", id_f.value).execute()
            if not res.data:
                res = supabase.table("社員ログイン情報").select("*").eq("社員ID", int(id_f.value)).execute()
            if res.data and str(res.data[0].get("パスワード")).strip() == pw_f.value:
                state["user_id"] = str(res.data[0].get("社員ID"))
                state["user_name"] = res.data[0].get("氏名")
                show_dashboard()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("ログイン失敗"))
                page.snack_bar.open = True
                page.update()
        page.add(ft.Column([
            ft.Container(height=80),
            ft.Icon(ft.Icons.BUSINESS, size=80, color="blue"),
            ft.Text("勤怠管理システム", size=30, weight="bold"),
            id_f, pw_f,
            ft.FilledButton("ログイン", on_click=login_c, width=300, height=50),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        page.update()

    show_login()

if __name__ == "__main__":
    ft.run(main)