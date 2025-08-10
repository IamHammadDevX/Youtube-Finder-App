import customtkinter as ctk
from core.youtube_api import YouTubeAPI

class YouTubeFinderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Finder - Modern UI")
        self.geometry("1200x700")  # Increased window width to accommodate more columns
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar (for controls)
        self.sidebar = ctk.CTkScrollableFrame(self, width=320, corner_radius=15)
        self.sidebar.grid(row=0, column=0, sticky="nswe", padx=(20, 10), pady=20)

        self._create_sidebar()

        # Main area (for results and status)
        self.main_area = ctk.CTkFrame(self, corner_radius=15)
        self.main_area.grid(row=0, column=1, sticky="nswe", padx=(10, 20), pady=20)
        self.main_area.grid_propagate(True)

        self._create_main_area()
        self.api = YouTubeAPI()
        self.start_button.configure(command=self.on_start_now)

    def on_start_now(self):
        # Get all keywords (strip empty lines)
        keywords = [kw.strip() for kw in self.keywords_text.get("1.0", "end").splitlines() if kw.strip()]
        # Clear previous results once
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        found_any = False
        row = 0
        for keyword in keywords:
            video_ids = self.api.search_videos(keyword)
            if not video_ids:
                self._add_table_row(["No results", "-", "-", "-", "-", "-", keyword], row=row, video_id=None)
                row += 1
                continue
            details = self.api.get_videos_details(video_ids[:1])  # Change to [:3] for top 3
            channel_ids = [item["snippet"]["channelId"] for item in details]
            channel_details = self.api.get_channels_details(channel_ids)
            subs_dict = {item["id"]: item["statistics"]["subscriberCount"] for item in channel_details if "statistics" in item and "subscriberCount" in item["statistics"]}
            for item in details:
                title = item["snippet"]["title"]
                channel = item["snippet"]["channelTitle"]
                views = self._format_number(item["statistics"].get("viewCount", "0"))
                subs = self._format_number(subs_dict.get(item["snippet"]["channelId"], "0"))
                duration = self._format_duration(item["contentDetails"]["duration"])
                published = item["snippet"]["publishedAt"][:10]
                video_id = item["id"]  # Get the actual video ID
                self._add_table_row([title, channel, views, subs, duration, published, keyword], row=row, video_id=video_id)
                row += 1
                found_any = True
        if not found_any:
            self._add_table_row(["No results", "-", "-", "-", "-", "-", "-"], row=0, video_id=None)

    def _format_number(self, num):
        if num == "0" or num == "-":
            return num
        num = float(num)
        if num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        return f"{int(num)}"

    def _format_duration(self, duration):
        import isodate
        duration_seconds = isodate.parse_duration(duration).total_seconds()
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        return f"{minutes}:{seconds:02d}"

    def _create_sidebar(self):
        # Title
        ctk.CTkLabel(self.sidebar, text="Controls", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(16, 10))

        # 1. Keywords
        ctk.CTkLabel(self.sidebar, text="Keywords (one per line):").pack(anchor="w", padx=12)
        self.keywords_text = ctk.CTkTextbox(self.sidebar, height=70, width=270)
        self.keywords_text.pack(padx=12, pady=(2, 10))

        # 2. Duration Options
        ctk.CTkLabel(self.sidebar, text="Video Duration:").pack(anchor="w", padx=12)
        self.duration_var = ctk.StringVar(value="any")
        self.duration_options = ctk.CTkOptionMenu(
            self.sidebar, variable=self.duration_var,
            values=["Any", "Short (<4m)", "Medium (4-20m)", "Long (>20m)", "Custom"]
        )
        self.duration_options.pack(padx=12, pady=(2, 5))
        # Custom min/max (hidden unless Custom is selected)
        self.custom_duration_frame = ctk.CTkFrame(self.sidebar)
        ctk.CTkLabel(self.custom_duration_frame, text="Min (min):").grid(row=0, column=0, padx=2)
        self.custom_min = ctk.CTkEntry(self.custom_duration_frame, width=35)
        self.custom_min.grid(row=0, column=1, padx=2)
        ctk.CTkLabel(self.custom_duration_frame, text="Max (min):").grid(row=0, column=2, padx=2)
        self.custom_max = ctk.CTkEntry(self.custom_duration_frame, width=35)
        self.custom_max.grid(row=0, column=3, padx=2)
        self.custom_duration_frame.pack_forget()  # hidden initially

        def on_duration_change(*_):
            if self.duration_var.get() == "Custom":
                self.custom_duration_frame.pack(padx=12, pady=(2, 8))
            else:
                self.custom_duration_frame.pack_forget()
        self.duration_var.trace_add("write", on_duration_change)

        # 3. Views Min/Max
        ctk.CTkLabel(self.sidebar, text="Views (Min/Max):").pack(anchor="w", padx=12)
        views_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.views_min = ctk.CTkEntry(views_frame, width=50, placeholder_text="Min")
        self.views_min.grid(row=0, column=0, padx=2)
        self.views_max = ctk.CTkEntry(views_frame, width=50, placeholder_text="Max")
        self.views_max.grid(row=0, column=1, padx=2)
        views_frame.pack(padx=12, pady=(2, 8), anchor="w")

        # 4. Subscribers Min/Max
        ctk.CTkLabel(self.sidebar, text="Subscribers (Min/Max):").pack(anchor="w", padx=12)
        subs_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.subs_min = ctk.CTkEntry(subs_frame, width=50, placeholder_text="Min")
        self.subs_min.grid(row=0, column=0, padx=2)
        self.subs_max = ctk.CTkEntry(subs_frame, width=50, placeholder_text="Max")
        self.subs_max.grid(row=0, column=1, padx=2)
        subs_frame.pack(padx=12, pady=(2, 8), anchor="w")

        # 5. Region / Language dropdowns
        ctk.CTkLabel(self.sidebar, text="Region:").pack(anchor="w", padx=12)
        self.region_var = ctk.StringVar(value="")
        self.region_menu = ctk.CTkOptionMenu(
            self.sidebar, variable=self.region_var,
            values=["", "US", "GB", "IN", "DE", "JP", "FR", "KR", "BR", "RU", "Other..."]
        )
        self.region_menu.pack(padx=12, pady=(2, 5), anchor="w")

        ctk.CTkLabel(self.sidebar, text="Language:").pack(anchor="w", padx=12)
        self.lang_var = ctk.StringVar(value="")
        self.lang_menu = ctk.CTkOptionMenu(
            self.sidebar, variable=self.lang_var,
            values=["", "en", "es", "fr", "de", "ru", "ja", "pt", "ko", "Other..."]
        )
        self.lang_menu.pack(padx=12, pady=(2, 8), anchor="w")

        # 6. Pages per keyword
        ctk.CTkLabel(self.sidebar, text="Pages per keyword:").pack(anchor="w", padx=12)
        self.pages_entry = ctk.CTkEntry(self.sidebar, width=60, placeholder_text="e.g. 2")
        self.pages_entry.pack(padx=12, pady=(2, 8), anchor="w")

        # 7. Daily API cap
        ctk.CTkLabel(self.sidebar, text="Daily API cap:").pack(anchor="w", padx=12)
        self.api_cap_entry = ctk.CTkEntry(self.sidebar, width=80, placeholder_text="e.g. 9500")
        self.api_cap_entry.pack(padx=12, pady=(2, 10), anchor="w")

        # 8. Checkboxes
        self.skip_hidden_var = ctk.BooleanVar(value=True)
        self.skip_hidden_check = ctk.CTkCheckBox(self.sidebar, text="Skip hidden subs", variable=self.skip_hidden_var)
        self.skip_hidden_check.pack(anchor="w", padx=12)
        self.fresh_search_var = ctk.BooleanVar(value=False)
        self.fresh_search_check = ctk.CTkCheckBox(self.sidebar, text="Fresh search (clear history)", variable=self.fresh_search_var)
        self.fresh_search_check.pack(anchor="w", padx=12, pady=(0, 10))

        # 9. Buttons
        self.start_button = ctk.CTkButton(self.sidebar, text="Start Now", width=200)
        self.start_button.pack(pady=(12, 6))
        self.schedule_button = ctk.CTkButton(self.sidebar, text="Save Schedule...", width=200)
        self.schedule_button.pack(pady=(0, 16))

    def _create_main_area(self):
        # ---------- STATUS BAR ----------
        status_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        status_frame.pack(fill="x", pady=(10, 0), padx=10)

        self.quota_label = ctk.CTkLabel(
            status_frame, text="Estimated quota: 0 / 0",
            font=ctk.CTkFont(size=14, weight="bold"))
        self.quota_label.pack(side="left", padx=(0, 15))

        self.counters_label = ctk.CTkLabel(
            status_frame, text="Scanned: 0  |  Kept: 0  |  Skipped: 0",
            font=ctk.CTkFont(size=14))
        self.counters_label.pack(side="left", padx=(0, 15))

        self.progress_var = ctk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(
            status_frame, variable=self.progress_var, width=250)
        self.progress_bar.pack(side="right", padx=(15, 0))
        self.progress_bar.set(0)

        # ---------- TABLE WRAPPER ----------
        # Outer frame hosts both scrollbars
        wrapper = ctk.CTkFrame(self.main_area)
        wrapper.pack(fill="both", expand=True, padx=10, pady=(10, 15))

        # Canvas + Scrollbars
        self.table_canvas = ctk.CTkCanvas(
            wrapper, highlightthickness=0, bg="white")
        h_scroll = ctk.CTkScrollbar(
            wrapper, orientation="horizontal", command=self.table_canvas.xview)
        v_scroll = ctk.CTkScrollbar(
            wrapper, orientation="vertical", command=self.table_canvas.yview)

        self.table_canvas.configure(
            xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        self.table_canvas.pack(side="top", fill="both", expand=True)
        h_scroll.pack(side="bottom", fill="x")
        v_scroll.pack(side="right", fill="y")

        # Inner frame that will hold every row
        self.table_frame = ctk.CTkFrame(self.table_canvas)
        self.canvas_window = self.table_canvas.create_window(
            (0, 0), window=self.table_frame, anchor="nw")

        # Column widths
        self.col_widths = [300, 150, 80, 80, 80, 100, 120, 60]

        # ---- Header ----
        bold = ctk.CTkFont(size=13, weight="bold")
        for idx, text in enumerate(
                ["Title", "Channel", "Views", "Subs",
                 "Duration", "Published", "Keyword", "Open"]):
            ctk.CTkLabel(
                self.table_frame, text=text, font=bold,
                anchor="w", padx=6, pady=8, width=self.col_widths[idx]
            ).grid(row=0, column=idx, sticky="nsew")

        # Auto-update scroll-region
        self.table_frame.bind("<Configure>",
                              lambda e: self.table_canvas.configure(
                                  scrollregion=self.table_canvas.bbox("all")))

    def _update_scrollregion(self, event=None):
        """Update the scrollregion of the canvas to encompass the inner frame"""
        self.table_canvas.update_idletasks()
        self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all"))

    def _add_table_row(self, values, row=0, video_id=None):
        normal = ctk.CTkFont(size=13)

        for idx, val in enumerate(values):
            wrap = 300 if idx == 0 else 120
            ctk.CTkLabel(
                self.table_frame, text=str(val), font=normal,
                anchor="w", padx=6, pady=6,
                wraplength=wrap, width=self.col_widths[idx]
            ).grid(row=row + 1, column=idx, sticky="nsew")

        if video_id:
            ctk.CTkButton(
                self.table_frame, text="Open", width=60, height=24,
                command=lambda v=video_id: self._open_video(v)
            ).grid(row=row + 1, column=len(values), padx=6, pady=4, sticky="e")

    def _open_video(self, video_id):
        import webbrowser
        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")

def main():
    app = YouTubeFinderApp()
    app.mainloop()

if __name__ == "__main__":
    main()