import pandas as pd
import customtkinter as ctk
from tkinter import messagebox
from core.youtube_api import YouTubeAPI
from core.filters import filter_videos
from core.csv_utils import (
    save_results_csv,
    read_seen_history,
    append_seen_history,
    log_run
)
import os

class YouTubeFinderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Finder - Modern UI")
        self.geometry("1200x700")
        
        # Initialize channel_id_map
        self.channel_id_map = {}  # Dictionary to store channel name to ID mapping

        # Initialize column widths
        self.col_widths = [300, 150, 80, 80, 80, 100, 120, 60]

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create UI components
        self._create_sidebar()
        self._create_main_area()
        
        # Initialize API and buttons
        self.api = YouTubeAPI()
        self.start_button.configure(command=self.on_start_now)
        self.schedule_button.configure(command=self.on_save_schedule)
        
        # Initialize data structures
        self.df = pd.DataFrame()

    def on_save_schedule(self):
        """Save current settings to JSON and create batch file for scheduling"""
        settings = {
            "api_cap": self._parse_int(self.api_cap_entry.get()) or 9500,
            "keywords": [kw.strip() for kw in self.keywords_text.get("1.0", "end").splitlines() if kw.strip()],
            "duration": self.duration_var.get(),
            "duration_min": self._parse_int(self.custom_min.get()) if self.duration_var.get() == "Custom" else None,
            "duration_max": self._parse_int(self.custom_max.get()) if self.duration_var.get() == "Custom" else None,
            "views_min": self._parse_int(self.views_min.get()),
            "views_max": self._parse_int(self.views_max.get()),
            "subs_min": self._parse_int(self.subs_min.get()),
            "subs_max": self._parse_int(self.subs_max.get()),
            "region": self.region_var.get(),
            "language": self.lang_var.get(),
            "pages_per_keyword": self._parse_int(self.pages_entry.get()) or 1,
            "skip_hidden_subs": self.skip_hidden_var.get(),
            "fresh_search": self.fresh_search_var.get()
        }

        # Save settings to JSON
        with open("settings.json", "w", encoding="utf-8") as f:
            import json
            json.dump(settings, f, indent=2)

        # Create batch file for scheduling
        bat_content = f"""@echo off
set PYTHONPATH={os.path.abspath(os.getcwd())}
python app/scheduler/headless.py --settings settings.json
"""
        with open("youtube_finder_task.bat", "w") as f:
            f.write(bat_content)

        messagebox.showinfo(
            "Schedule Saved",
            "1. Settings saved to settings.json\n"
            "2. Created youtube_finder_task.bat\n\n"
            "To automate:\n"
            "a) Open Task Scheduler\n"
            "b) Create a new task\n"
            "c) Trigger: Daily at your preferred time\n"
            "d) Action: Start 'youtube_finder_task.bat'"
        )

    def on_start_now(self):
        """Execute search with current parameters"""
        keywords = [kw.strip() for kw in self.keywords_text.get("1.0", "end").splitlines() if kw.strip()]
        if not keywords:
            messagebox.showwarning("Warning", "Please enter at least one keyword")
            return

        # Clear and prepare table
        self._clear_table(keep_header=True)
        self.progress_bar.set(0)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

        # Get and validate filters
        filters = self._get_current_filters()
        
        # Validate views and subscribers for negative values
        if (filters['views_min'] is not None and filters['views_min'] < 0) or \
        (filters['views_max'] is not None and filters['views_max'] < 0) or \
        (filters['subs_min'] is not None and filters['subs_min'] < 0) or \
        (filters['subs_max'] is not None and filters['subs_max'] < 0):
            messagebox.showwarning("Invalid Input", "Negative values for views or subscribers are not allowed. Please correct the input.")
            self._clear_table(keep_header=True)  # Clear any partial render
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            return

        # Check seen history
        seen_history_path = "data/seen_history.csv"
        if filters['fresh_search'] and os.path.exists(seen_history_path):
            os.remove(seen_history_path)
        seen_ids = read_seen_history(seen_history_path)

        all_results = []
        found_any = False
        quota_estimate = self.api.estimate_run_cost(keywords, filters['pages_per_keyword'])
        self.quota_label.configure(text=f"Estimated quota: {quota_estimate}")

        # Process each keyword
        for keyword in keywords:
            try:
                # Search for videos
                video_ids = self.api.search_videos(
                    keyword,
                    regionCode=filters['region'],
                    relevanceLanguage=filters['language'],
                )
                
                # Deduplication
                video_ids = [vid for vid in video_ids if vid not in seen_ids]
                if not video_ids:
                    self._add_table_row(["No new videos found", "-", "-", "-", "-", "-", keyword], video_id=None)
                    continue

                # Get video details
                details = self.api.get_videos_details(video_ids[:50])
                channel_ids = [item["snippet"]["channelId"] for item in details if "snippet" in item]
                channel_details = self.api.get_channels_details(channel_ids)

                # Build channel info
                chinfo = {
                    item["id"]: {
                        "subscriberCount": item["statistics"].get("subscriberCount", "0"),
                        "hiddenSubscriberCount": item["statistics"].get("hiddenSubscriberCount", False),
                    }
                    for item in channel_details
                }

                # Filter videos
                filtered = filter_videos(
                    details,
                    views_min=filters['views_min'],
                    views_max=filters['views_max'],
                    duration_min=filters['duration_min'],
                    duration_max=filters['duration_max'],
                    region=filters['region'],
                    language=filters['language'],
                    subs_min=filters['subs_min'],
                    subs_max=filters['subs_max'],
                    skip_hidden_subs=filters['skip_hidden_subs'],
                    channels_info=chinfo,
                )

                if not filtered:
                    self._add_table_row(["No matching videos found", "-", "-", "-", "-", "-", keyword], video_id=None)
                    continue

                # Process filtered results
                for item in filtered:
                    result = self._process_video_item(item, keyword, chinfo)
                    all_results.append(result)
                    self._add_table_row([
                        result['title'],
                        result['channel_title'],
                        self._format_number(result['view_count']),
                        self._format_number(result['subscriber_count']),
                        self._human_duration(result['duration_minutes'] * 60),
                        result['published_at'],
                        keyword
                    ], video_id=result['video_id'])
                    append_seen_history(result['video_id'], out_file=seen_history_path)
                    found_any = True

            except Exception as e:
                messagebox.showerror("API Error", f"Failed to fetch results: {str(e)}")
                continue

        # Finalize
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        
        # Save results and log
        if all_results:
            save_results_csv(all_results, keyword=";".join(keywords))
        log_run(
            keywords_count=len(keywords),
            results_count=len(all_results),
            quota_used=self.api.quota_used
        )

        if not found_any:
            self._add_table_row(["No results found", "-", "-", "-", "-", "-", "-"], video_id=None)

    def _get_current_filters(self):
        """Extract current filter values from UI with validation for negative values"""
        duration_mode = self.duration_var.get()
        duration_min, duration_max = None, None
        if duration_mode == "Short (<4m)":
            duration_min, duration_max = 0, 4
        elif duration_mode == "Medium (4-20m)":
            duration_min, duration_max = 4, 20
        elif duration_mode == "Long (>20m)":
            duration_min, duration_max = 20, None
        elif duration_mode == "Custom":
            duration_min = self._parse_int(self.custom_min.get())
            duration_max = self._parse_int(self.custom_max.get())

        # Parse and validate views
        views_min = self._parse_int(self.views_min.get())
        views_max = self._parse_int(self.views_max.get())
        if views_min is not None and views_min < 0:
            messagebox.showwarning("Invalid Input", "Minimum views cannot be negative. Using no minimum.")
            views_min = None
        if views_max is not None and views_max < 0:
            messagebox.showwarning("Invalid Input", "Maximum views cannot be negative. Using no maximum.")
            views_max = None

        # Parse and validate subscribers
        subs_min = self._parse_int(self.subs_min.get())
        subs_max = self._parse_int(self.subs_max.get())
        if subs_min is not None and subs_min < 0:
            messagebox.showwarning("Invalid Input", "Minimum subscribers cannot be negative. Using no minimum.")
            subs_min = None
        if subs_max is not None and subs_max < 0:
            messagebox.showwarning("Invalid Input", "Maximum subscribers cannot be negative. Using no maximum.")
            subs_max = None

        return {
            'views_min': views_min,
            'views_max': views_max,
            'subs_min': subs_min,
            'subs_max': subs_max,
            'duration_min': duration_min,
            'duration_max': duration_max,
            'region': self.region_var.get() if self.region_var.get() else None,
            'language': self.lang_var.get() if self.lang_var.get() else None,
            'skip_hidden_subs': self.skip_hidden_var.get(),
            'fresh_search': self.fresh_search_var.get(),
            'pages_per_keyword': self._parse_int(self.pages_entry.get()) or 1
        }

    def _process_video_item(self, item, keyword, chinfo):
        """Extract relevant data from video item"""
        snippet = item["snippet"]
        stats = item["statistics"]
        content = item["contentDetails"]
        channel_id = snippet["channelId"]
        
        duration_seconds = 0
        try:
            import isodate
            duration_seconds = int(isodate.parse_duration(content["duration"]).total_seconds())
        except Exception:
            pass

        # Update channel_id_map with the channel title and ID
        self.channel_id_map[snippet["channelTitle"]] = channel_id

        return {
            "title": snippet["title"],
            "description": snippet["description"],
            "tags": snippet.get("tags", []),
            "video_url": f"https://www.youtube.com/watch?v={item['id']}",
            "video_id": item["id"],
            "channel_title": snippet["channelTitle"],
            "channel_id": channel_id,
            "subscriber_count": chinfo.get(channel_id, {}).get("subscriberCount", "0"),
            "view_count": stats.get("viewCount", "0"),
            "duration_minutes": duration_seconds // 60,
            "published_at": snippet["publishedAt"][:10],
            "keyword": keyword,
        }

    def _create_sidebar(self):
        """Create the left sidebar with controls"""
        self.sidebar = ctk.CTkScrollableFrame(self, width=320, corner_radius=15)
        self.sidebar.grid(row=0, column=0, sticky="nswe", padx=(20, 10), pady=20)

        # Title
        ctk.CTkLabel(self.sidebar, text="Controls", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(16, 10))

        # 1. Keywords
        ctk.CTkLabel(self.sidebar, text="Keywords (one per line):").pack(anchor="w", padx=12)
        self.keywords_text = ctk.CTkTextbox(self.sidebar, height=70, width=270)
        self.keywords_text.pack(padx=12, pady=(2, 10))
        self.keywords_text.bind("<KeyRelease>", lambda e: self._update_quota_estimate())

        # 2. Duration Options
        ctk.CTkLabel(self.sidebar, text="Video Duration:").pack(anchor="w", padx=12)
        self.duration_var = ctk.StringVar(value="Any")
        self.duration_options = ctk.CTkOptionMenu(
            self.sidebar, variable=self.duration_var,
            values=["Any", "Short (<4m)", "Medium (4-20m)", "Long (>20m)", "Custom"]
        )
        self.duration_options.pack(padx=12, pady=(2, 5))
        
        # Custom duration inputs
        self.custom_duration_frame = ctk.CTkFrame(self.sidebar)
        ctk.CTkLabel(self.custom_duration_frame, text="Min (min):").grid(row=0, column=0, padx=2)
        self.custom_min = ctk.CTkEntry(self.custom_duration_frame, width=35)
        self.custom_min.grid(row=0, column=1, padx=2)
        ctk.CTkLabel(self.custom_duration_frame, text="Max (min):").grid(row=0, column=2, padx=2)
        self.custom_max = ctk.CTkEntry(self.custom_duration_frame, width=35)
        self.custom_max.grid(row=0, column=3, padx=2)
        self.custom_duration_frame.pack_forget()
        
        self.duration_var.trace_add("write", lambda *_: self._toggle_custom_duration())

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

        # 5. Region/Language
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
        self.pages_entry.bind("<KeyRelease>", lambda e: self._update_quota_estimate())

        # 7. Daily API cap
        ctk.CTkLabel(self.sidebar, text="Daily API cap:").pack(anchor="w", padx=12)
        self.api_cap_entry = ctk.CTkEntry(self.sidebar, width=80, placeholder_text="e.g. 9500")
        self.api_cap_entry.pack(padx=12, pady=(2, 10), anchor="w")

        # 8. Checkboxes
        self.skip_hidden_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.sidebar, text="Skip hidden subs", variable=self.skip_hidden_var).pack(anchor="w", padx=12)
        
        self.fresh_search_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.sidebar, text="Fresh search (clear history)", variable=self.fresh_search_var).pack(anchor="w", padx=12, pady=(0, 10))

        # 9. Buttons
        self.start_button = ctk.CTkButton(self.sidebar, text="Start Now", width=200)
        self.start_button.pack(pady=(12, 6))
        
        self.schedule_button = ctk.CTkButton(self.sidebar, text="Save Schedule...", width=200)
        self.schedule_button.pack(pady=(0, 16))

    def _create_main_area(self):
        """Create the main results area"""
        self.main_area = ctk.CTkFrame(self, corner_radius=15)
        self.main_area.grid(row=0, column=1, sticky="nswe", padx=(10, 20), pady=20)
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # Status bar
        status_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        status_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        self.quota_label = ctk.CTkLabel(
            status_frame, 
            text="Estimated quota: 0", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.quota_label.pack(side="left", padx=(0, 15))

        self.counters_label = ctk.CTkLabel(
            status_frame, 
            text="Scanned: 0 | Kept: 0 | Skipped: 0",
            font=ctk.CTkFont(size=14)
        )
        self.counters_label.pack(side="left", padx=(0, 15))

        self.progress_var = ctk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(
            status_frame, 
            variable=self.progress_var, 
            width=250,
            mode="determinate"
        )
        self.progress_bar.pack(side="right", padx=(15, 0))
        self.progress_bar.set(0)

        # Filter controls
        filter_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 0))
        
        ctk.CTkLabel(filter_frame, text="Filter:").pack(side="left", padx=5)
        self.filter_var = ctk.StringVar()
        self.filter_entry = ctk.CTkEntry(
            filter_frame, 
            width=200, 
            textvariable=self.filter_var,
            placeholder_text="Filter results..."
        )
        self.filter_entry.pack(side="left", padx=5)
        self.filter_var.trace_add("write", self._apply_table_filter)

        # Results table
        self.table_frame = ctk.CTkScrollableFrame(
            self.main_area,
            orientation="vertical",
            height=500
        )
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self._render_table_header()

    def _render_table_header(self):
        """Render the table header row with dynamic column widths"""
        header_frame = ctk.CTkFrame(self.table_frame)
        header_frame.pack(fill="x")

        # Define column headers and their relative weights
        headers = ["Title", "Channel", "Views", "Subs", "Duration", "Published", "Keyword", "Actions"]
        weights = [3, 2, 1, 1, 1, 1, 2, 1]  # Proportional weights for each column

        bold = ctk.CTkFont(size=13, weight="bold")
        for idx, (text, weight) in enumerate(zip(headers, weights)):
            label = ctk.CTkLabel(
                header_frame,
                text=text,
                font=bold,
                anchor="w"
            )
            label.grid(row=0, column=idx, padx=2, sticky="ew")
            header_frame.grid_columnconfigure(idx, weight=weight, minsize=80)  # Minimum width of 80 pixels

    def _add_table_row(self, values, video_id=None):
        """Add a row to the results table with dynamic text handling"""
        row_frame = ctk.CTkFrame(self.table_frame)
        row_frame.pack(fill="x", pady=1)

        headers = ["Title", "Channel", "Views", "Subs", "Duration", "Published", "Keyword", "Actions"]
        weights = [3, 2, 1, 1, 1, 1, 2, 1]  # Same weights as header

        for idx, (val, weight) in enumerate(zip(values, weights)):
            if headers[idx] in ["Title", "Channel"] and len(str(val)) > 50:
                val = str(val)[:47] + "..."
            label = ctk.CTkLabel(
                row_frame,
                text=str(val),
                anchor="w"
            )
            label.grid(row=0, column=idx, padx=2, sticky="w")
            row_frame.grid_columnconfigure(idx, weight=weight, minsize=80)

        if video_id:
            btn_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            btn_frame.grid(row=0, column=7, padx=2, sticky="e")  # Align with "Actions" column

            # Video button
            ctk.CTkButton(
                btn_frame,
                text="Video",
                width=60,
                height=24,
                command=lambda v=video_id: self._open_video(v)
            ).grid(row=0, column=0, padx=2, pady=2)

            # Channel button - use channel name to look up ID
            channel_name = values[1]  # Channel name is at index 1
            channel_id = self.channel_id_map.get(channel_name)
            ctk.CTkButton(
                btn_frame,
                text="Channel",
                width=60,
                height=24,
                command=lambda c=channel_id: self._open_channel(c) if c else None
            ).grid(row=0, column=1, padx=2, pady=2)

            # Ensure btn_frame takes up the full "Actions" column space
            row_frame.grid_columnconfigure(7, weight=1)

    def _clear_table(self, keep_header=False):
        """Clear the results table"""
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        if keep_header:
            self._render_table_header()

    def _apply_table_filter(self, *args):
        """Apply filter to the results table"""
        filter_text = self.filter_var.get().lower()
        
        # Get all children except the header (first child)
        children = self.table_frame.winfo_children()
        header = children[0] if children else None
        
        for widget in children:
            if isinstance(widget, ctk.CTkFrame) and widget != header:
                # Check each column's text for filter match
                match_found = False
                for i in range(7):  # Check all columns except actions
                    try:
                        label = widget.grid_slaves(row=0, column=i)
                        if label and filter_text in label[0].cget("text").lower():
                            match_found = True
                            break
                    except Exception:
                        continue
                
                # Show/hide based on filter match
                if not filter_text or match_found:
                    widget.pack(fill="x", pady=1)
                else:
                    widget.pack_forget()

    def _update_quota_estimate(self):
        """Update the estimated quota usage display"""
        keywords = [kw.strip() for kw in self.keywords_text.get("1.0", "end").splitlines() if kw.strip()]
        pages = self._parse_int(self.pages_entry.get()) or 1
        estimate = self.api.estimate_run_cost(keywords, pages)
        self.quota_label.configure(text=f"Estimated quota: {estimate}")

    def _toggle_custom_duration(self):
        """Show/hide custom duration inputs based on selection"""
        if self.duration_var.get() == "Custom":
            self.custom_duration_frame.pack(padx=12, pady=(2, 8))
        else:
            self.custom_duration_frame.pack_forget()

    def _parse_int(self, val):
        """Safely parse integer from string"""
        try:
            return int(val) if val else None
        except (ValueError, TypeError):
            return None

    def _format_number(self, num):
        """Format large numbers with K/M suffixes"""
        if num == "0" or num == "-":
            return num
        try:
            num = float(str(num).replace(",", ""))
        except Exception:
            return str(num)
        if num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        return f"{int(num)}"

    def _parse_duration_seconds(self, duration):
        """Parse ISO duration string to seconds"""
        import isodate
        try:
            return int(isodate.parse_duration(duration).total_seconds())
        except Exception:
            return 0

    def _human_duration(self, secs):
        """Convert seconds to MM:SS format"""
        mins = secs // 60
        s = secs % 60
        return f"{mins}:{s:02d}"

    def _open_video(self, video_id):
        """Open video in default browser"""
        import webbrowser
        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")

    def _open_channel(self, channel_id):
        """Open channel in default browser using channel ID"""
        import webbrowser
        if channel_id:
            webbrowser.open(f"https://www.youtube.com/channel/{channel_id}")
        else:
            messagebox.showwarning("Warning", "Channel ID not found")

def main():
    """Main application entry point"""
    app = YouTubeFinderApp()
    app.mainloop()

if __name__ == "__main__":
    main()