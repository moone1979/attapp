import os
import flet as ft
import flet.geolocator as fg  # 新しいFletでのGPSインポート
from datetime import datetime
import zoneinfo
import re 
from supabase import create_client

# --- Supabase接続設定 ---
URL = "https://novsbhmrsyurgmjextxg.supabase.co"
KEY = "sb_publishable_Kt4eOMIPaS50FJCb4drWGw_sGcLDWdb"
supabase = create_client(URL, KEY)
JST = zoneinfo.ZoneInfo("Asia/Tokyo")

def main(page: ft.Page):
    page.title = "社内勤怠システム"
    page.theme_mode = ft.ThemeMode.LIGHT
    
    # GPSコンポーネントの初期化
    gd = fg.Geolocator()
    page.overlay.append(gd)

    state = {"user_id": "", "user_name": "", "user_dept": "", "edit_mode": False}

    # --- 画面遷移用ナビ ---
    def on_nav_change(e):
        if e.control.selected_index == 0:
            show_dashboard()
        else:
            show_history()

    def get_nav(index):
        return ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.TIMER_OUTLINED, label="打刻"),
                ft.NavigationBarDestination(icon=ft.Icons.HISTORY_OUTLINED, label="履歴"),
            ],
            selected_index=index,
            on_change=on_nav_change,
        )

    # --- 1. 打刻画面 ---
    def show_dashboard():
        page.clean()
        page.navigation_bar = get_nav(0)
        today = datetime.now(JST).strftime("%Y-%m-%d")
        
        # 既存データ取得
        res = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).eq("日付", today).execute()
        in_time = res.data[0].get("出勤時刻") or "" if res.data else ""
        out_time = res.data[0].get("退勤時刻") or "" if res.data else ""
        has_in, has_out = in_time != "", out_time != ""

        # GPS打刻処理
        async def handle_stamp(stamp_type):
            page.open(ft.SnackBar(ft.Text("位置情報を確認中...")))
            page.update()
            
            lat = lon = None
            try:
                # タイムアウトなしのシンプルな取得（iPhoneで安定する方法）
                pos = await gd.get_current_position_async()
                if pos:
                    lat, lon = pos.latitude, pos.longitude
            except Exception as e:
                print(f"GPS Error: {e}")

            now_time = datetime.now(JST).strftime("%H:%M")
            data = {
                "社員ID": state["user_id"], 
                "氏名": state["user_name"], 
                "日付": today,
            }
            
            # 位置情報があれば追加、なければ既存を維持
            if lat and lon:
                data["緯度"], data["経度"] = lat, lon
            elif res.data:
                data["緯度"] = res.data[0].get("緯度")
                data["経度"] = res.data[0].get("経度")

            if stamp_type == "in":
                data["出勤時刻"] = now_time
            else:
                data["退勤時刻"] = now_time

            # 保存 (upsert)
            supabase.table("attendance_log").upsert(data, on_conflict="社員ID, 日付").execute()
            page.open(ft.SnackBar(ft.Text("完了しました")))
            show_dashboard()

        # UI構築
        page.add(
            ft.Column([
                ft.Container(height=20),
                ft.Text(f"{state['user_name']} さん", size=20, weight="bold"),
                ft.Divider(),
                ft.FilledButton(
                    "出勤打刻", 
                    icon=ft.Icons.PLAY_ARROW,
                    on_click=lambda _: page.run_task(handle_stamp, "in"),
                    disabled=has_in,
                    width=300, height=70, bgcolor="green"
                ),
                ft.Container(height=10),
                ft.FilledButton(
                    "退勤打刻", 
                    icon=ft.Icons.STOP,
                    on_click=lambda _: page.run_task(handle_stamp, "out"),
                    disabled=has_out,
                    width=300, height=70, bgcolor="red"
                ),
                ft.Card(
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Text(f"出勤：{in_time or '--:--'}"),
                            ft.Text(f"退勤：{out_time or '--:--'}"),
                        ])
                    )
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    # --- 2. ログイン画面 ---
    def show_login():
        page.clean()
        id_f = ft.TextField(label="社員ID", value="19671219")
        pw_f = ft.TextField(label="パスワード", password=True, value="19671219")

        async def login_click(e):
            # IDを数値と文字列両方で試行（Supabaseの型エラー回避）
            res = supabase.table("社員ログイン情報").select("*").eq("社員ID", id_f.value).execute()
            if not res.data:
                res = supabase.table("社員ログイン情報").select("*").eq("社員ID", int(id_f.value)).execute()
            
            if res.data and str(res.data[0].get("パスワード")).strip() == pw_f.value:
                state.update({
                    "user_id": str(res.data[0].get("社員ID")),
                    "user_name": res.data[0].get("氏名"),
                    "user_dept": res.data[0].get("部署")
                })
                show_dashboard()
            else:
                page.open(ft.SnackBar(ft.Text("ログイン失敗")))

        page.add(ft.Column([id_f, pw_f, ft.FilledButton("ログイン", on_click=login_click)], horizontal_alignment="center"))

    show_login()

if __name__ == "__main__":
    # Render環境用のポート設定
    port = int(os.getenv("PORT", 8550))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")