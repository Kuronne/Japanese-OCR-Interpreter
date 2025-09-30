import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
import threading
import os
from PIL import Image, ImageTk
from datetime import datetime
from typing import Optional, List

from jp_interpreter import JpInterpreterCore, ProcessingResult
from jp_interpreter_settings_manager import SettingsManager

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False
    TkinterDnD = None
    DND_FILES = None

class HistoryEntry:
    def __init__(self, image_path: str, result: ProcessingResult):
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        self.image_path = image_path
        self.filename = os.path.basename(image_path)
        self.text = result.combined_text
        self.success = result.success
        self.processing_time = result.processing_time
        self.detection_count = len(result.results)

class JPInterpreterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🇯🇵 Japanese OCR Interpreter")
        self.root.geometry("900x600")
        
        # Initialize settings manager first
        self.settings_manager = SettingsManager()
        
        # Application state
        self.ocr_core: Optional[JpInterpreterCore] = None
        self.current_image_path: Optional[str] = None
        self.processing = False
        self.history: List[HistoryEntry] = []
        
        # Apply saved theme
        saved_theme = self.settings_manager.get('theme', 'cosmo')
        self.style = ttk.Style(saved_theme)
        self.available_themes = ["cosmo", "darkly", "solar", "cyborg", "vapor", "superhero", "flatly"]
        try:
            self.current_theme_index = self.available_themes.index(saved_theme)
        except ValueError:
            self.current_theme_index = 0
        
        self.setup_ui()
        self.setup_drag_drop()
        self.init_ocr_async()
        
        # Simple closing handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_closing(self):
        if messagebox.askokcancel("Quit", "Are you sure you want to quit?"):
            self.root.quit()
            self.root.destroy()
    
    def setup_ui(self):
        self.create_header()
        self.create_toolbar()
        self.create_main_content()
        self.create_progress_bar()
    
    def create_header(self):
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=X, padx=10, pady=5)
        
        title_label = ttk.Label(header_frame, text="🇯🇵 Japanese OCR Interpreter", font=("Arial", 16, "bold"))
        title_label.pack(side=LEFT)
    
    def create_toolbar(self):
        toolbar_frame = ttk.Frame(self.root)
        toolbar_frame.pack(fill=X, padx=10, pady=5)
        
        # Main action buttons
        self.browse_btn = ttk.Button(toolbar_frame, text="📂 Browse Images", command=self.browse_images, 
                                   bootstyle=PRIMARY, state=DISABLED)
        self.browse_btn.pack(side=LEFT, padx=5)
        
        self.clear_btn = ttk.Button(toolbar_frame, text="🗑️ Clear", command=self.clear_results, bootstyle=SECONDARY)
        self.clear_btn.pack(side=LEFT, padx=5)
        
        self.settings_btn = ttk.Button(toolbar_frame, text="⚙️ Settings", command=self.show_settings, bootstyle=INFO)
        self.settings_btn.pack(side=LEFT, padx=5)

        # Status label
        self.status_label = ttk.Label(toolbar_frame, text="Initializing OCR engine...", foreground="orange")
        self.status_label.pack(side=RIGHT, padx=5)

    def create_main_content(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # OCR Tab
        self.create_ocr_tab()
        
        # History Tab
        self.create_history_tab()
    
    def create_ocr_tab(self):
        self.ocr_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ocr_frame, text="📷 OCR")
        
        # Create main horizontal container
        main_container = ttk.Frame(self.ocr_frame)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # Left side - Image areas (50% width)
        self.left_frame = ttk.Frame(main_container)
        self.left_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))
        
        # Right side - Results area (50% width)
        self.right_frame = ttk.Frame(main_container)
        self.right_frame.pack(side=RIGHT, fill=BOTH, expand=True, padx=(5, 0))
        
        self.create_image_input_area()
        self.create_image_preview_area()
        self.create_results_area()
    
    def create_image_input_area(self):
        self.drop_frame = ttk.LabelFrame(self.left_frame, text="📷 Image Input", bootstyle=PRIMARY)
        self.drop_frame.pack(fill=X, pady=(0, 10))
        
        drop_text = "📥 Drag & Drop Images Here\nor click Browse Images button"
        if not DRAG_DROP_AVAILABLE:
            drop_text = "📂 Click Browse Images button\n(Drag & Drop not available)"
        
        self.drop_label = ttk.Label(self.drop_frame, text=drop_text, font=("Arial", 12), anchor=CENTER)
        self.drop_label.pack(expand=True, fill=BOTH, padx=20, pady=30)
    
    def create_image_preview_area(self):
        self.preview_frame = ttk.LabelFrame(self.left_frame, text="🖼️ Image Preview", bootstyle=INFO)
        self.preview_frame.pack(fill=BOTH, expand=True)
        
        self.preview_label = ttk.Label(self.preview_frame, text="No image selected", anchor=CENTER)
        self.preview_label.pack(padx=10, pady=20, fill=BOTH, expand=True)
    
    def create_results_area(self):
        self.results_frame = ttk.LabelFrame(self.right_frame, text="📖 Japanese Text Detected", bootstyle=SUCCESS)
        self.results_frame.pack(fill=BOTH, expand=True)
        
        # Text area with scrollbar
        text_frame = ttk.Frame(self.results_frame)
        text_frame.pack(fill=BOTH, expand=True, padx=10, pady=(10, 5))
        
        self.results_text = ttk.Text(text_frame, wrap=WORD, font=("Arial", 14), height=12)
        scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Action buttons at bottom of results frame
        self.create_action_buttons()
    
    def create_action_buttons(self):
        buttons_frame = ttk.Frame(self.results_frame)
        buttons_frame.pack(fill=X, padx=10, pady=(5, 10), side=BOTTOM)
        
        self.copy_btn = ttk.Button(buttons_frame, text="📋 Copy to Clipboard", command=self.copy_to_clipboard,
                                 bootstyle=SUCCESS, state=DISABLED)
        self.copy_btn.pack(fill=X, pady=2)
        
        self.save_btn = ttk.Button(buttons_frame, text="💾 Save Results", command=self.save_results,
                                 bootstyle=INFO, state=DISABLED)
        self.save_btn.pack(fill=X, pady=2)
        
        self.translate_dropdown_button(buttons_frame)
    
    def translate_dropdown_button(self, parent_frame):
        translate_frame = ttk.Frame(parent_frame)
        translate_frame.pack(fill=X, pady=2)
        
        self.languages = {'Romanian': 'ro', 'English': 'en'}
        self.selected_language_code = 'en'
        
        # Dropdown pentru selecția limbii
        language_label = ttk.Label(translate_frame, text="Language:", font=("Arial", 9))
        language_label.pack(side=LEFT, padx=(0, 5))
        
        self.language_var = ttk.StringVar(value="English")
        self.language_dropdown = ttk.Combobox(translate_frame, textvariable=self.language_var,
                                            values=list(self.languages.keys()), state="readonly", width=12, font=("Arial", 9))
        self.language_dropdown.pack(side=LEFT, padx=(0, 5))
        
        self.language_dropdown.bind('<<ComboboxSelected>>', self.on_language_changed)
        
        # Buton translate cu flag
        self.translate_btn = ttk.Button(translate_frame, text="🌍 Translate", command=self.translate_text,
                                      bootstyle=WARNING, state=DISABLED)
        self.translate_btn.pack(side=LEFT, fill=X, expand=True, padx=(5, 0))
    
    def on_language_changed(self, event):
        selected_lang = self.language_var.get()
        self.selected_language_code = self.languages[selected_lang]
        
        # Update flag-ul pe buton
        flags = {'ro': '🇷🇴', 'en': '🇺🇸'}
        flag = flags.get(self.selected_language_code, '🌍')
        self.translate_btn.config(text=f"{flag} Translate")
    
    def create_history_tab(self):
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="📚 History")
        
        # History controls
        history_controls = ttk.Frame(self.history_frame)
        history_controls.pack(fill=X, padx=10, pady=5)
        
        ttk.Label(history_controls, text="📚 Processing History", font=("Arial", 12, "bold")).pack(side=LEFT)
        
        clear_history_btn = ttk.Button(history_controls, text="🗑️ Clear History", 
                                     command=self.clear_history, bootstyle=DANGER)
        clear_history_btn.pack(side=RIGHT)
        
        # History table
        columns = ("Time", "Image", "Text", "Status")
        self.history_tree = ttk.Treeview(self.history_frame, columns=columns, show="headings", bootstyle=INFO)
        
        # Configure columns
        self.history_tree.heading("Time", text="🕒 Time")
        self.history_tree.heading("Image", text="📷 Image")
        self.history_tree.heading("Text", text="📖 Japanese Text")
        self.history_tree.heading("Status", text="📊 Status")
        
        self.history_tree.column("Time", width=100)
        self.history_tree.column("Image", width=150)
        self.history_tree.column("Text", width=350)
        self.history_tree.column("Status", width=100)
        
        # Scrollbar for history
        history_scroll = ttk.Scrollbar(self.history_frame, orient=VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scroll.set)
        
        self.history_tree.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)
        history_scroll.pack(side=RIGHT, fill=Y, pady=10)
        
        # Bind double-click
        self.history_tree.bind("<Double-1>", self.on_history_double_click)
    
    def create_progress_bar(self):
        self.progress = ttk.Progressbar(self.root, mode='indeterminate', bootstyle=SUCCESS)
        # Initially hidden
        self.progress.pack_forget()
    
    def setup_drag_drop(self):
        if DRAG_DROP_AVAILABLE:
            try:
                self.drop_label.drop_target_register(DND_FILES)
                self.drop_label.dnd_bind('<<Drop>>', self.on_drop)
            except Exception as e:
                print(f"Failed to setup drag & drop: {e}")
    
    def init_ocr_async(self):
        def init_ocr():
            try:
                self.status_label.config(text="Loading OCR models...", foreground="orange")
                self.ocr_core = JpInterpreterCore(gpu=False, verbose=True)
                self.root.after(0, self.on_ocr_ready)
            except Exception as e:
                error_msg = f"OCR initialization failed: {str(e)}"
                self.root.after(0, self.on_ocr_error, error_msg)
        
        threading.Thread(target=init_ocr, daemon=True).start()
    
    def on_ocr_ready(self):
        self.status_label.config(text="Ready - OCR initialized!", foreground="green")
        self.browse_btn.config(state=NORMAL)
        
        # Update drop label
        if DRAG_DROP_AVAILABLE:
            self.drop_label.config(text="📥 Drag & Drop Images Here\nor click Browse Images button")
        else:
            self.drop_label.config(text="📂 Click Browse Images button")
    
    def on_ocr_error(self, error_msg: str):
        self.status_label.config(text="OCR initialization failed", foreground="red")
        messagebox.showerror("Initialization Error", error_msg)
    
    def browse_images(self):
        if self.processing or not self.ocr_core:
            return
        
        file_types = [
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.gif"),
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg *.jpeg"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(title="Select Japanese Image", filetypes=file_types)
        if filename:
            self.process_image_async(filename)
    
    def on_drop(self, event):
        if self.processing or not self.ocr_core:
            return
        
        files = event.data.split()
        if files:
            filename = files[0].strip('{}')  # Remove braces on Windows
            if os.path.isfile(filename):
                self.process_image_async(filename)
    
    def process_image_async(self, image_path: str):
        if self.processing:
            return

        self.processing = True
        self.current_image_path = image_path
        
        # Show progress
        self.show_processing_state()
        
        # Show image preview
        self.show_image_preview(image_path)
        
        def process_thread():
            try:
                result = self.ocr_core.process_image(image_path)
                self.root.after(0, self.on_processing_complete, result, image_path)
            except Exception as e:
                error_msg = f"Processing failed: {str(e)}"
                self.root.after(0, self.on_processing_error, error_msg)
        
        threading.Thread(target=process_thread, daemon=True).start()
    
    def show_processing_state(self):
        self.progress.pack(fill=X, padx=10, pady=5)
        self.progress.start()
        
        self.status_label.config(text="Processing image...", foreground="orange")
        self.browse_btn.config(state=DISABLED)
        
        # Disable action buttons
        for btn in [self.copy_btn, self.save_btn, self.translate_btn]:
            btn.config(state=DISABLED)
    
    def show_image_preview(self, image_path: str):
        try:
            # Load and resize image for preview
            image = Image.open(image_path)
            image.thumbnail((350, 300), Image.Resampling.LANCZOS)
            
            # Convert for Tkinter
            photo = ImageTk.PhotoImage(image)
            
            # Display image
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo  # Keep reference
            
        except Exception as e:
            self.preview_label.config(image="", text=f"Preview not available\n{os.path.basename(image_path)}")
            self.preview_label.image = None
    
    def on_processing_complete(self, result: ProcessingResult, image_path: str):
        self.processing = False
        self.hide_processing_state()
        
        if result.success and result.results:
            # Display results
            self.display_results(result)
            
            # Add to history
            if self.settings_manager.get('save_history', True):
                self.add_to_history(image_path, result)
            
            # Auto-copy if enabled
            if self.settings_manager.get('auto_copy', False):
                self.copy_to_clipboard()
            
            # Update status
            detection_count = len([r for r in result.results if r.is_japanese])
            processing_time = f"{result.processing_time:.2f}s" if result.processing_time else "N/A"
            
            self.status_label.config(text=f"Success! Found {detection_count} Japanese text(s) in {processing_time}", 
                                   foreground="green")
        else:
            # No results found
            self.results_text.delete(1.0, END)
            self.results_text.insert(1.0, "No Japanese text detected in this image.")
            
            # Disable action buttons
            for btn in [self.copy_btn, self.save_btn, self.translate_btn]:
                btn.config(state=DISABLED)
            
            self.status_label.config(text="No Japanese text found", foreground="orange")
            
            # Add failed result to history
            if self.settings_manager.get('save_history', True):
                self.add_to_history(image_path, result)
        
        self.root.update_idletasks()
    
    def on_processing_error(self, error_msg: str):
        self.processing = False
        self.hide_processing_state()
        
        self.status_label.config(text="Processing failed", foreground="red")
        messagebox.showerror("Processing Error", error_msg)
    
    def hide_processing_state(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.browse_btn.config(state=NORMAL)
    
    def display_results(self, result: ProcessingResult):
        self.results_text.delete(1.0, END)
        self.results_text.insert(1.0, result.combined_text)
        
        # Enable action buttons
        for btn in [self.copy_btn, self.save_btn, self.translate_btn]:
            btn.config(state=NORMAL)
        
        self.results_frame.update_idletasks()
    
    def add_to_history(self, image_path: str, result: ProcessingResult):
        entry = HistoryEntry(image_path, result)
        self.history.append(entry)
        
        # Add to treeview
        status_text = f"✅ {entry.detection_count} found" if entry.success else "❌ Failed"
        display_text = entry.text[:40] + "..." if len(entry.text) > 40 else entry.text
        
        self.history_tree.insert("", 0, values=(entry.timestamp, entry.filename, display_text, status_text))
    
    def on_history_double_click(self, event):
        selection = self.history_tree.selection()
        if not selection:
            return
        
        item = self.history_tree.item(selection[0])
        timestamp = item['values'][0]
        
        # Find corresponding history entry
        for entry in self.history:
            if entry.timestamp == timestamp:
                # Show image preview and results
                if os.path.exists(entry.image_path):
                    self.show_image_preview(entry.image_path)
                
                self.results_text.delete(1.0, END)
                self.results_text.insert(1.0, entry.text)
                
                # Enable buttons if there's text
                if entry.text and entry.success:
                    for btn in [self.copy_btn, self.save_btn, self.translate_btn]:
                        btn.config(state=NORMAL)
                
                # Switch to OCR tab
                self.notebook.select(0)
                break
    
    def copy_to_clipboard(self):
        text = self.results_text.get(1.0, END).strip()
        if text and text != "No Japanese text detected in this image.":
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_label.config(text="Copied to clipboard!", foreground="green")
        else:
            messagebox.showwarning("Nothing to Copy", "No text available to copy.")
    
    def save_results(self):
        text = self.results_text.get(1.0, END).strip()
        if not text or text == "No Japanese text detected in this image.":
            messagebox.showwarning("Nothing to Save", "No text available to save.")
            return
        
        filename = filedialog.asksaveasfilename(title="Save Japanese Text", defaultextension=".txt",
                                              filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.status_label.config(text="Results saved successfully!", foreground="green")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save file:\n{str(e)}")
    
    def translate_text(self):
        self.translate_btn.config(text="Translating...", state="disabled")
        self.processing = True
        
        text = self.results_text.get(1.0, END)
        
        if not text or text == "No Japanese text detected in this image.":
            self.translation_error("No text available to translate")
            return
        
        def translation_thread():
            try:
                translated = self.ocr_core.translate_extracted_results(text, target_language=self.selected_language_code)
                self.root.after(0, self.show_translation, translated)
                self.root.after(0, self.update_status, "Translation completed!", "green")
            except Exception as e:
                self.root.after(0, self.translation_error, str(e))
                self.root.after(0, self.update_status, "Translation failed", "red")

        threading.Thread(target=translation_thread, daemon=True).start()

    def update_status(self, message, color):
        self.status_label.config(text=message, foreground=color)

    def show_translation(self, translated):
        content = self.results_text.get(1.0, END)

        # Extract the original text without translation
        for marker in ["\n----------------------"]:
            if marker in content:
                content = content.split(marker)[0].strip()
                translated = self.ocr_core.translate_extracted_results(content, target_language=self.selected_language_code)
                break

        # Rewrite text with new translation
        self.results_text.delete(1.0, END)
        self.results_text.insert(END, content + 
            f"\n----------------------\n"
            f"🌍 Translation:\n"
            f"----------------------\n{translated}")
    
        self.reset_translate_button()

    def translation_error(self, error):
        messagebox.showerror("Translation Error", error)
        self.reset_translate_button()

    def reset_translate_button(self):
        self.translate_btn.config(text="🌍 Translate", state="normal")
        self.processing = False

    def clear_results(self):
        self.results_text.delete(1.0, END)
        self.preview_label.config(image="", text="No image selected")
        self.preview_label.image = None
        self.current_image_path = None
        
        # Disable action buttons
        for btn in [self.copy_btn, self.save_btn, self.translate_btn]:
            btn.config(state=DISABLED)
        
        self.status_label.config(text="Results cleared", foreground="green")
    
    def clear_history(self):
        if not self.history:
            return
        
        if messagebox.askyesno("Clear History", "Are you sure you want to clear all history?"):
            self.history.clear()
            
            # Clear treeview
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            self.status_label.config(text="History cleared", foreground="green")
    
    def show_settings(self):
        # Create settings window
        settings_win = ttk.Toplevel(self.root)
        settings_win.title("⚙️ Settings")
        settings_win.geometry("450x300")
        settings_win.transient(self.root)
        settings_win.grab_set()
        
        # Interface Settings
        ui_frame = ttk.LabelFrame(settings_win, text="🖥️ Interface Settings", bootstyle=INFO)
        ui_frame.pack(fill=X, padx=15, pady=10)
        
        # Define all variables first
        auto_copy_var = ttk.BooleanVar(value=self.settings_manager.get('auto_copy', False))
        save_history_var = ttk.BooleanVar(value=self.settings_manager.get('save_history', True))
        theme_var = ttk.StringVar(value=self.settings_manager.get('theme', 'cosmo'))
        
        # Create checkboxes
        ttk.Checkbutton(ui_frame, text="Automatically copy results to clipboard",
                       variable=auto_copy_var, bootstyle="round-toggle").pack(anchor=W, padx=10, pady=5)
        
        ttk.Checkbutton(ui_frame, text="Save processing history",
                       variable=save_history_var, bootstyle="round-toggle").pack(anchor=W, padx=10, pady=5)
        
        # Theme selection
        theme_frame = ttk.LabelFrame(settings_win, text="🎨 Appearance", bootstyle=SUCCESS)
        theme_frame.pack(fill=X, padx=15, pady=10)
        
        ttk.Label(theme_frame, text="Theme:").pack(anchor=W, padx=10, pady=(10, 5))
        
        theme_combo = ttk.Combobox(theme_frame, textvariable=theme_var,
                                 values=self.available_themes, state="readonly")
        theme_combo.pack(fill=X, padx=10, pady=(0, 10))
        
        def on_theme_change(event):
            try:
                new_theme = theme_var.get()
                self.style.theme_use(new_theme)
                try:
                    self.current_theme_index = self.available_themes.index(new_theme)
                except ValueError:
                    pass
            except:
                pass
        
        theme_combo.bind('<<ComboboxSelected>>', on_theme_change)
        
        # Buttons frame
        btn_frame = ttk.Frame(settings_win)
        btn_frame.pack(fill=X, padx=15, pady=15)
        
        # Define button actions
        def save_settings_action():
            self.settings_manager.update_multiple({
                'auto_copy': auto_copy_var.get(),
                'save_history': save_history_var.get(),
                'theme': theme_var.get()
            })
            self.status_label.config(text="Settings saved successfully!", foreground="green")
            settings_win.destroy()
        
        def reset_settings_action():
            auto_copy_var.set(False)
            save_history_var.set(True)
            theme_var.set("cosmo")
            self.style.theme_use("cosmo")
            self.current_theme_index = 0
        
        # Create buttons
        ttk.Button(btn_frame, text="💾 Save", command=save_settings_action, bootstyle=SUCCESS).pack(side=RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="🔄 Reset", command=reset_settings_action, bootstyle=WARNING).pack(side=RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="❌ Cancel", command=settings_win.destroy, bootstyle=SECONDARY).pack(side=RIGHT, padx=(5, 0))

def create_app():
    if DRAG_DROP_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = ttk.Window()
    
    app = JPInterpreterApp(root)
    return app, root

def main():
    try:
        app, root = create_app()
        root.mainloop()
    except ImportError as e:
        print(f"Import error: {e}")
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()
        
        if 'root' in locals():
            try:
                root.destroy()
            except:
                pass

if __name__ == "__main__":
    main()