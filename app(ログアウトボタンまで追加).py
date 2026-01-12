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
    page.window_width = 450
    page.window_height = 800
    page.theme_mode = ft.ThemeMode.LIGHT
    
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

    # ログアウト処理
    def logout(e):
        state["user_id"] = ""
        state["user_name"] = ""
        state["user_dept"] = ""
        state["edit_mode"] = False
        show_login()

    # --- 1. 打刻画面 ---
    def show_dashboard():
        page.controls.clear()
        page.scroll = ft.ScrollMode.AUTO
        page.navigation_bar = get_nav(0)
        
        # 名前と部署、ログアウトボタンを表示（インデントを修正）
        display_name = f"{state['user_name']} さん ({state.get('user_dept', '未設定')})"
        page.appbar = ft.AppBar(
            title=ft.Text(display_name, size=16),
            bgcolor="#E1E2E5",
            automatically_imply_leading=False,
            actions=[
                ft.TextButton("ログアウト", icon=ft.Icons.LOGOUT, on_click=logout, icon_color="red", style=ft.ButtonStyle(color="red"))
            ]
        )
        
        today = datetime.now(JST).strftime("%Y-%m-%d")
        res = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).eq("日付", today).execute()
        
        in_time = out_time = ""
        if res.data:
            in_time = res.data[0].get("出勤時刻") or ""
            out_time = res.data[0].get("退勤時刻") or ""

        has_in, has_out = in_time != "", out_time != ""

        in_field = ft.TextField(value=in_time, label="出勤", width=140, text_align="center", dense=True)
        out_field = ft.TextField(value=out_time, label="退勤", width=140, text_align="center", dense=True)

        def save_manual(e):
            valid_re = r'^([01]\d|2[0-3]):([0-5]\d)$'
            if (in_field.value and not re.match(valid_re, in_field.value)) or \
               (out_field.value and not re.match(valid_re, out_field.value)):
                page.snack_bar = ft.SnackBar(ft.Text("HH:MM形式で入力してください"), bgcolor="red")
                page.snack_bar.open = True
                page.update()
                return
            
            supabase.table("attendance_log").delete().eq("社員ID", state["user_id"]).eq("日付", today).execute()
            supabase.table("attendance_log").insert({
                "社員ID": state["user_id"], "氏名": state["user_name"], "日付": today,
                "出勤時刻": in_field.value or None, "退勤時刻": out_field.value or None
            }).execute()
            state["edit_mode"] = False
            show_dashboard()

        if state["edit_mode"]:
            history_content = ft.Column([
                ft.Text("時刻修正", weight="bold"),
                in_field, out_field,
                ft.Row([
                    ft.FilledButton("保存", on_click=save_manual, style=ft.ButtonStyle(bgcolor="green", color="white")),
                    ft.TextButton("キャンセル", on_click=lambda _: [state.update({"edit_mode": False}), show_dashboard()]),
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
        else:
            history_content = ft.Column([
                ft.Row([ft.Icon(ft.Icons.LOGIN, color="green"), ft.Text(f"出勤: {in_time or '--:--'}", size=18)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([ft.Icon(ft.Icons.LOGOUT, color="red"), ft.Text(f"退勤: {out_time or '--:--'}", size=18)], alignment=ft.MainAxisAlignment.CENTER),
            ], spacing=10)

        page.add(
            ft.Column([
                ft.Container(height=10),
                ft.Text("本日の打刻", size=25, weight="bold"),
                ft.Divider(height=20),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW), ft.Text("出勤打刻", size=20)], alignment=ft.MainAxisAlignment.CENTER),
                    on_click=lambda _: handle_stamp("in"),
                    disabled=has_in or state["edit_mode"],
                    style=ft.ButtonStyle(bgcolor="green" if not has_in else "grey", color="white"),
                    width=320, height=80
                ),
                ft.Container(height=10),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.STOP), ft.Text("退勤打刻", size=20)], alignment=ft.MainAxisAlignment.CENTER),
                    on_click=lambda _: handle_stamp("out"),
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
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                ft.Card(content=ft.Container(content=history_content, padding=15), width=320),
                ft.Container(height=20),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
        page.update()

    # --- 2. 勤務履歴画面 ---
    def show_history():
        page.controls.clear()
        page.navigation_bar = get_nav(1)
        
        display_name = f"{state['user_name']} さん ({state.get('user_dept', '未設定')})"
        page.appbar = ft.AppBar(
            title=ft.Text(display_name, size=16),
            bgcolor="#E1E2E5",
            automatically_imply_leading=False,
            actions=[
                ft.TextButton("ログアウト", icon=ft.Icons.LOGOUT, on_click=logout, icon_color="red", style=ft.ButtonStyle(color="red"))
            ]
        )

        table_container = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        total_overtime_label = ft.Text("合計残業時間: 0.00 時間", size=18, weight="bold", color="blue")
        
        def calculate_overtime(in_str, out_str):
            if not in_str or not out_str:
                return 0.0
            def to_minutes(t_str):
                h, m = map(int, t_str.split(":"))
                return h * 60 + m
            in_min = to_minutes(in_str)
            out_min = to_minutes(out_str)
            over_min = 0
            dept = state.get("user_dept", "")
            if dept == "リサイクル事業部":
                limit_in, base_in = to_minutes("07:15"), to_minutes("07:30")
                if in_min <= limit_in:
                    over_min += ((base_in - in_min) // 15) * 15
                limit_out, base_out = to_minutes("17:15"), to_minutes("17:00")
                if out_min >= limit_out:
                    over_min += ((out_min - base_out) // 15) * 15
            else:
                duration = out_min - in_min
                if duration >= 555:
                    over_min = ((duration - 540) // 15) * 15
            return over_min / 60.0

        def load_history_data(e):
            if not month_dropdown.value: return
            sel_year, sel_month = map(int, month_dropdown.value.split("/"))
            if sel_month == 1: start_date = f"{sel_year - 1}-12-26"
            else: start_date = f"{sel_year}-{sel_month - 1:02d}-26"
            end_date = f"{sel_year}-{sel_month:02d}-25"
            
            res = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).gte("日付", start_date).lte("日付", end_date).order("日付", desc=False).execute()
            
            data_table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("日付", weight="bold")),
                    ft.DataColumn(ft.Text("出勤", weight="bold")),
                    ft.DataColumn(ft.Text("退勤", weight="bold")),
                    ft.DataColumn(ft.Text("残業", weight="bold")),
                ],
                rows=[], column_spacing=30, horizontal_lines=ft.BorderSide(1, "grey200"),
            )
            total_over = 0.0
            if res.data:
                for item in res.data:
                    d_obj = datetime.strptime(item['日付'], "%Y-%m-%d")
                    date_display = f"{d_obj.strftime('%m/%d')}({['月','火','水','木','金','土','日'][d_obj.weekday()]})"
                    ov_time = calculate_overtime(item.get('出勤時刻'), item.get('退勤時刻'))
                    total_over += ov_time
                    data_table.rows.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(date_display)),
                        ft.DataCell(ft.Text(item.get('出勤時刻') or "--:--", color="green")),
                        ft.DataCell(ft.Text(item.get('退勤時刻') or "--:--", color="red")),
                        ft.DataCell(ft.Text(f"{ov_time:.2f}", weight="bold")),
                    ]))
            table_container.controls.clear()
            if not res.data: 
                table_container.controls.append(ft.Container(content=ft.Text("履歴がありません"), padding=20))
                total_overtime_label.value = "合計残業時間: 0.00 時間"
            else: 
                table_container.controls.append(data_table)
                total_overtime_label.value = f"合計残業時間: {total_over:.2f} 時間"
            page.update()

        now = datetime.now(JST)
        options = [ft.dropdown.Option(f"{(now.year if (now.month-i)>0 else now.year-1)}/{((now.month-i-1)%12+1):02d}") for i in range(6)]
        month_dropdown = ft.Dropdown(label="給与月", options=options, width=160, value=options[0].key)

        page.add(
            ft.Column([
                ft.Container(height=10),
                ft.Row([month_dropdown, ft.FilledButton("表示", on_click=load_history_data, icon=ft.Icons.SEARCH)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(),
                ft.Row([ft.Text("勤務一覧", size=16, weight="bold"), total_overtime_label], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(content=table_container, margin=ft.Margin(0, 10, 0, 0), alignment=ft.Alignment(0, -1), expand=True)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        )
        load_history_data(None)
        page.update()

    def handle_stamp(stamp_type):
        today = datetime.now(JST).strftime("%Y-%m-%d")
        now_time = datetime.now(JST).strftime("%H:%M")
        res = supabase.table("attendance_log").select("*").eq("社員ID", state["user_id"]).eq("日付", today).execute()
        if res.data:
            supabase.table("attendance_log").update({("出勤時刻" if stamp_type=="in" else "退勤時刻"): now_time}).eq("社員ID", state["user_id"]).eq("日付", today).execute()
        else:
            supabase.table("attendance_log").insert({"社員ID": state["user_id"], "氏名": state["user_name"], "日付": today, ("出勤時刻" if stamp_type=="in" else "退勤時刻"): now_time}).execute()
        show_dashboard()

    def show_login():
        page.controls.clear()
        page.navigation_bar = None
        page.appbar = None # ログイン画面ではAppBarを消す
        id_f = ft.TextField(label="社員ID", value="19671219")
        pw_f = ft.TextField(label="パスワード", password=True, value="19671219")
        def login_c(e):
            res = supabase.table("社員ログイン情報").select("*").eq("社員ID", id_f.value).execute()
            if not res.data: res = supabase.table("社員ログイン情報").select("*").eq("社員ID", int(id_f.value)).execute()
            if res.data and str(res.data[0].get("パスワード")).strip() == pw_f.value:
                state["user_id"] = str(res.data[0].get("社員ID"))
                state["user_name"] = res.data[0].get("氏名")
                state["user_dept"] = res.data[0].get("部署") 
                show_dashboard()
        page.add(ft.Column([ft.Container(height=80), ft.Text("勤怠管理システム", size=30, weight="bold"), id_f, pw_f, ft.FilledButton("ログイン", on_click=login_c, width=300)], horizontal_alignment="center"))
        page.update()

    show_login()

if __name__ == "__main__":
    ft.run(main)