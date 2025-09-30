import json
import os
from typing import Dict, Any

class SettingsManager:
    
    def __init__(self, app_name: str = "JapaneseOCRInterpreter"):
        self.app_name = app_name
        self.settings_file = self._get_settings_file_path()
        self.default_settings = self._get_default_settings()
        self.current_settings = self.default_settings.copy()
        
        # Load existing settings
        self.load_settings()
    
    def _get_settings_file_path(self) -> str:
        
        # Get the directory where the Python script is located
        app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create settings file in the same directory as the application
        settings_file = os.path.join(app_dir, 'jp_interpreter_settings.json')
        
        return settings_file
    
    def _get_default_settings(self) -> Dict[str, Any]:
        return {
            # Appearance settings
            'theme': 'cosmo',
            'window_width': 900,
            'window_height': 600,
            'window_maximized': False,
            
            # OCR settings
            'confidence_threshold': 0.2,
            'include_non_japanese': False,
            'use_gpu': False,
            
            # Interface settings
            'auto_copy': False,
            'save_history': True,
            'show_confidence': False,
            'show_processing_time': True,
            
            # File settings
            'last_browse_directory': '',
            'default_save_format': 'txt',
            
            # Advanced settings
            'max_history_items': 100,
            'auto_clear_results': False,
            'show_tooltips': True,
        }
    
    def load_settings(self) -> bool:
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                # Merge with defaults to ensure all keys exist
                self.current_settings = self.default_settings.copy()
                self.current_settings.update(loaded_settings)
                return True
            else:
                # Use defaults if no settings file exists
                self.current_settings = self.default_settings.copy()
                return False
                
        except Exception as e:
            print(f"Warning: Failed to load settings: {e}")
            print("Using default settings.")
            self.current_settings = self.default_settings.copy()
            return False
    
    def save_settings(self) -> bool:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_settings, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Warning: Failed to save settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.current_settings.get(key, default)
    
    def set(self, key: str, value: Any, save_immediately: bool = True) -> bool:
        self.current_settings[key] = value
        
        if save_immediately:
            return self.save_settings()
        return True
    
    def update_multiple(self, settings_dict: Dict[str, Any], save_immediately: bool = True) -> bool:
        self.current_settings.update(settings_dict)
        
        if save_immediately:
            return self.save_settings()
        return True
    
    def reset_to_defaults(self, save_immediately: bool = True) -> bool:
        self.current_settings = self.default_settings.copy()
        
        if save_immediately:
            return self.save_settings()
        return True
    
    def get_all_settings(self) -> Dict[str, Any]:
        return self.current_settings.copy()
    
    def export_settings(self, file_path: str) -> bool:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to export settings: {e}")
            return False
    
    def import_settings(self, file_path: str, save_immediately: bool = True) -> bool:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_settings = json.load(f)
            
            # Validate and merge with current settings
            valid_keys = set(self.default_settings.keys())
            filtered_settings = {k: v for k, v in imported_settings.items() if k in valid_keys}
            
            self.current_settings.update(filtered_settings)
            
            if save_immediately:
                return self.save_settings()
            return True
            
        except Exception as e:
            print(f"Failed to import settings: {e}")
            return False
    
    def get_settings_file_info(self) -> Dict[str, Any]:
        info = {
            'file_path': self.settings_file,
            'exists': os.path.exists(self.settings_file),
            'size_bytes': 0,
            'last_modified': None
        }
        
        if info['exists']:
            try:
                stat = os.stat(self.settings_file)
                info['size_bytes'] = stat.st_size
                info['last_modified'] = stat.st_mtime
            except:
                pass
        
        return info

# Convenience functions for quick access
_global_settings_manager = None

def get_settings_manager() -> SettingsManager:
    global _global_settings_manager
    if _global_settings_manager is None:
        _global_settings_manager = SettingsManager()
    return _global_settings_manager

def get_setting(key: str, default: Any = None) -> Any:
    return get_settings_manager().get(key, default)

def set_setting(key: str, value: Any, save_immediately: bool = True) -> bool:
    return get_settings_manager().set(key, value, save_immediately)

def save_settings() -> bool:
    return get_settings_manager().save_settings()

