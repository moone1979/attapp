import os
import flet as ft
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
    page.window.width = 450
    page.window.height = 800
    page.theme_mode = ft.ThemeMode.LIGHT
    # スクロールを有効化
    page.scroll = ft.ScrollMode.ADAPTIVE
    
    # GPS初期化
    gd = ft.Geolocator()
    page.overlay.append(gd)

    state = {"user_id": "", "user_name": "", "user_dept": "", "edit_mode": False}

    def on_nav_change(e):
        if e.control.selected_index == 0:
            show_dashboard()
        else:
            show_history()

    def get_nav(index):
        return ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.TIMER_OUTLINED, selected_icon=ft.Icons.TIMER, label="打刻"),
                ft.NavigationBarDestination(icon=ft.Icons.HISTORY_OUTLINED, selected_icon=ft.Icons.HISTORY, label="履歴"),
            ],
            selected_index=index,
            on_change=on_nav_change,
        )

    def logout(e):
        state.update({"user_id": "", "user_name": "", "user_dept": "", "edit_mode": False})
        show_login()

    # --- 1. 打刻画面 ---
    def show_dashboard():
        page.clean()
        page.navigation_bar = get_nav(0)
        
        display_name = f"{state['user_name']} さん ({state.get('user_dept', '未設定')})"
        page.appbar = ft.AppBar(
            title=ft.Text(display_name, size=16),
            bgcolor="#E1E2E5",
            automatically_imply_leading=False,
            actions=[ft.TextButton("ログアウト", icon=ft.Icons.LOGOUT, on_click=logout, icon_color="red")]
        )
        
        today = datetime.now(JST).strftime("%Y-%m-%d")
        res = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).eq("日付", today).execute()
        
        in_time = out_time = ""
        if res.data:
            in_time = res.data[0].get("出勤時刻") or ""
            out_time = res.data[0].get("退勤時刻") or ""

        has_in, has_out = in_time != "", out_time != ""

        # 修正保存ロジック（重複防止・上書き確定版）
        async def save_manual(e):
            valid_re = r'^([01]\d|2[0-3]):([0-5]\d)$'
            if (in_field.value and not re.match(valid_re, in_field.value)) or \
               (out_field.value and not re.match(valid_re, out_field.value)):
                page.open(ft.SnackBar(ft.Text("HH:MM形式で入力してください"), bgcolor="red"))
                return
            
            # --- 1. IDの型を特定（文字列か数値か） ---
            # Supabase側が数値型の場合、int()に変換しないと一致しません
            try:
                target_id = int(state["user_id"])
            except:
                target_id = state["user_id"]

            # --- 2. 既存のGPS情報を取得 ---
            current_res = supabase.table("attendance_log").select("緯度, 経度").eq("社員ID", target_id).eq("日付", today).execute()
            lat = current_res.data[0].get("緯度") if current_res.data else None
            lon = current_res.data[0].get("経度") if current_res.data else None

            # --- 3. 重複防止のため、一旦その日のデータを削除 ---
            # これにより、確実に「今日のデータは1つ」になります
            supabase.table("attendance_log").delete().eq("社員ID", target_id).eq("日付", today).execute()

            # --- 4. 最新の位置情報を試行 ---
            try:
                # 確実に最新のメソッドを呼ぶため、少し丁寧な書き方にします
                pos = await gd.get_current_position_async()
            except Exception as e:
                print(f"GPS Error: {e}")
                pos = None
            if pos:
                lat, lon = pos.latitude, pos.longitude

            # --- 5. 新規データとして挿入（実質的な上書き） ---
            supabase.table("attendance_log").insert({
                "社員ID": target_id, 
                "氏名": state["user_name"], 
                "日付": today,
                "出勤時刻": in_field.value or None, 
                "退勤時刻": out_field.value or None,
                "緯度": lat,
                "経度": lon
            }).execute()

            state["edit_mode"] = False
            show_dashboard()

        async def handle_stamp_with_gps(stamp_type):
            today = datetime.now(JST).strftime("%Y-%m-%d")
            now_time = datetime.now(JST).strftime("%H:%M")
            
            # 1. 既存データをチェック
            check = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).eq("日付", today).execute()
            
            lat = lon = None
            if check.data:
                lat = check.data[0].get("緯度")
                lon = check.data[0].get("経度")

            # 2. 出勤時、かつ、まだ座標がない場合のみGPSを取得
            if stamp_type == "in" and lat is None:
                page.open(ft.SnackBar(ft.Text("出勤場所を確認中...")))
                try:
                    # 確実に最新のメソッドを呼ぶため、少し丁寧な書き方にします
                    pos = await gd.get_current_position_async()
                except Exception as e:
                    print(f"GPS Error: {e}")
                    pos = None
                if pos:
                    lat, lon = pos.latitude, pos.longitude
            
            # 3. 保存データの作成
            data = {
                "社員ID": state["user_id"], 
                "氏名": state["user_name"], 
                "日付": today,
                "緯度": lat,
                "経度": lon
            }
            
            if stamp_type == "in":
                data["出勤時刻"] = now_time
            else:
                data["退勤時刻"] = now_time

            # 4. Supabaseへ書き込み
            if check.data:
                supabase.table("attendance_log").update(data).eq("社員ID", state["user_id"]).eq("日付", today).execute()
            else:
                supabase.table("attendance_log").insert(data).execute()
            
            show_dashboard()

        in_field = ft.TextField(value=in_time, label="出勤", width=140, text_align="center", dense=True)
        out_field = ft.TextField(value=out_time, label="退勤", width=140, text_align="center", dense=True)

        if state["edit_mode"]:
            history_content = ft.Column([
                ft.Text("時刻修正", weight="bold"),
                in_field, out_field,
                ft.Row([
                    ft.FilledButton("保存", on_click=lambda e: page.run_task(save_manual, e), style=ft.ButtonStyle(bgcolor="green", color="white")),
                    ft.TextButton("キャンセル", on_click=lambda _: [state.update({"edit_mode": False}), show_dashboard()]),
                ], alignment="center")
            ], horizontal_alignment="center")
        else:
            history_content = ft.Column([
                ft.Row([ft.Icon(ft.Icons.LOGIN, color="green"), ft.Text(f"出勤: {in_time or '--:--'}", size=18)], alignment="center"),
                ft.Row([ft.Icon(ft.Icons.LOGOUT, color="red"), ft.Text(f"退勤: {out_time or '--:--'}", size=18)], alignment="center"),
            ])

        # メインコンテンツ
        page.add(
            ft.Column([
                ft.Container(height=10),
                ft.Text("本日の打刻", size=25, weight="bold"),
                ft.Divider(height=20),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW), ft.Text("出勤打刻", size=20)], alignment="center"),
                    on_click=lambda _: page.run_task(handle_stamp_with_gps, "in"),
                    disabled=has_in or state["edit_mode"],
                    style=ft.ButtonStyle(bgcolor="green" if not has_in else "grey", color="white"),
                    width=320, height=80
                ),
                ft.Container(height=10),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.STOP), ft.Text("退勤打刻", size=20)], alignment="center"),
                    on_click=lambda _: page.run_task(handle_stamp_with_gps, "out"),
                    disabled=has_out or state["edit_mode"],
                    style=ft.ButtonStyle(bgcolor="red" if not has_out else "grey", color="white"),
                    width=320, height=80
                ),
                ft.Divider(height=30),
                ft.Row([
                    ft.Text("本日の記録", size=20, weight="bold"),
                    ft.IconButton(ft.Icons.EDIT if not state["edit_mode"] else ft.Icons.CLOSE, 
                                  on_click=lambda _: [state.update({"edit_mode": not state["edit_mode"]}), show_dashboard()], 
                                  icon_color="blue")
                ], alignment="center", spacing=20),
                ft.Card(content=ft.Container(content=history_content, padding=15), width=320),
                ft.Container(height=40), # 下部に余白
            ], horizontal_alignment="center")
        )

    # --- 2. 勤務履歴画面 ---
    def show_history():
        page.clean()
        page.navigation_bar = get_nav(1)
        
        display_name = f"{state['user_name']} さん ({state.get('user_dept', '未設定')})"
        page.appbar = ft.AppBar(title=ft.Text(display_name, size=16), bgcolor="#E1E2E5", automatically_imply_leading=False, actions=[ft.TextButton("ログアウト", icon=ft.Icons.LOGOUT, on_click=logout, icon_color="red")])
        
        table_container = ft.Column(scroll=ft.ScrollMode.AUTO)
        total_overtime_label = ft.Text("合計残業時間: 0.00 時間", size=18, weight="bold", color="blue")

        def calculate_overtime(in_str, out_str):
            if not in_str or not out_str: return 0.0
            def to_minutes(t_str):
                h, m = map(int, t_str.split(":"))
                return h * 60 + m
            in_min, out_min = to_minutes(in_str), to_minutes(out_str)
            over_min = 0
            dept = state.get("user_dept", "")
            if dept == "リサイクル事業部":
                if in_min <= 435: over_min += ((450 - in_min) // 15) * 15
                if out_min >= 1035: over_min += ((out_min - 1020) // 15) * 15
            else:
                duration = out_min - in_min
                if duration >= 555: over_min = ((duration - 540) // 15) * 15
            return over_min / 60.0

        def load_history_data(e):
            if not month_dropdown.value: return
            sel_year, sel_month = map(int, month_dropdown.value.split("/"))
            start_date = f"{sel_year - 1}-12-26" if sel_month == 1 else f"{sel_year}-{sel_month - 1:02d}-26"
            end_date = f"{sel_year}-{sel_month:02d}-25"
            res = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).gte("日付", start_date).lte("日付", end_date).order("日付", desc=False).execute()
            
            data_table = ft.DataTable(columns=[ft.DataColumn(ft.Text("日付")), ft.DataColumn(ft.Text("出勤")), ft.DataColumn(ft.Text("退勤")), ft.DataColumn(ft.Text("残業"))], rows=[], column_spacing=15)
            total_over = 0.0
            if res.data:
                for item in res.data:
                    d_obj = datetime.strptime(item['日付'], "%Y-%m-%d")
                    ov = calculate_overtime(item.get('出勤時刻'), item.get('退勤時刻'))
                    total_over += ov
                    data_table.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(d_obj.strftime('%m/%d'))), ft.DataCell(ft.Text(item.get('出勤時刻') or "--:--", color="green")), ft.DataCell(ft.Text(item.get('退勤時刻') or "--:--", color="red")), ft.DataCell(ft.Text(f"{ov:.2f}"))]))
            table_container.controls = [data_table] if res.data else [ft.Text("履歴なし")]
            total_overtime_label.value = f"合計残業時間: {total_over:.2f} 時間"
            page.update()

        now = datetime.now(JST)
        options = [ft.dropdown.Option(f"{(now.year if (now.month-i)>0 else now.year-1)}/{((now.month-i-1)%12+1):02d}") for i in range(6)]
        month_dropdown = ft.Dropdown(label="給与月", options=options, width=160, value=options[0].key)
        
        page.add(
            ft.Column([
                ft.Container(height=10),
                ft.Row([month_dropdown, ft.FilledButton("表示", on_click=load_history_data)], alignment="center"),
                ft.Divider(),
                ft.Row([ft.Text("勤務一覧", weight="bold"), total_overtime_label], alignment="space-between"),
                table_container,
                ft.Container(height=40),
            ], horizontal_alignment="center")
        )
        load_history_data(None)

    def show_login():
        page.clean()
        page.navigation_bar = page.appbar = None
        id_f = ft.TextField(label="社員ID", value="19671219")
        pw_f = ft.TextField(label="パスワード", password=True, value="19671219")
        def login_c(e):
            res = supabase.table("社員ログイン情報").select("*").eq("社員ID", id_f.value).execute()
            if not res.data: res = supabase.table("社員ログイン情報").select("*").eq("社員ID", int(id_f.value)).execute()
            if res.data and str(res.data[0].get("パスワード")).strip() == pw_f.value:
                state.update({"user_id": str(res.data[0].get("社員ID")), "user_name": res.data[0].get("氏名"), "user_dept": res.data[0].get("部署")})
                show_dashboard()
        page.add(ft.Column([ft.Container(height=80), ft.Text("勤怠管理システム", size=30, weight="bold"), id_f, pw_f, ft.FilledButton("ログイン", on_click=login_c, width=300)], horizontal_alignment="center"))

    show_login()

if __name__ == "__main__":
    # Renderなどのクラウド環境では PORT 環境変数が指定されるためそれを使用
    port = int(os.getenv("PORT", 8550))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")