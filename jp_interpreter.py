import easyocr
import cv2
import numpy as np
import re
import os
from typing import List, Optional
from dataclasses import dataclass
import warnings
import time
from googletrans import Translator

# Suppress PyTorch pin_memory warnings when using CPU
warnings.filterwarnings("ignore", category=UserWarning, module="torch")

@dataclass
class OCRResult:
    text: str
    confidence: float
    bbox: List[List[float]]
    is_japanese: bool

@dataclass
class ProcessingResult:
    success: bool
    results: List[OCRResult]
    combined_text: str
    error_message: Optional[str] = None
    processing_time: Optional[float] = None

class JpInterpreterCore:
    
    def __init__(self, gpu: bool = False, verbose: bool = True):
        self.gpu = gpu
        self.verbose = verbose
        self.reader = None
        self._is_initialized = False
        
        if verbose:
            print("🔧 Initializing EasyOCR for Japanese text recognition...")
        
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        try:
            self.reader = easyocr.Reader(
                ['ja', 'en'], 
                gpu=self.gpu, 
                verbose=self.verbose
            )
            self._is_initialized = True
            
            if self.verbose:
                print("✅ EasyOCR initialized successfully!")
                
        except Exception as e:
            self._is_initialized = False
            raise RuntimeError(f"Failed to initialize EasyOCR: {str(e)}")
    
    @property
    def is_ready(self) -> bool:
        return self._is_initialized and self.reader is not None
    
    def detect_image_quality(self, image_path: str) -> str:
        
        # Load image
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Test OCR without preprocessing
        test_results = self.reader.readtext(gray, text_threshold=0.2)
        print(f"🔍 RAW: Found {len(test_results)} raw results:")
        for i, (_, text, conf) in enumerate(test_results):
            print(f"  [{i}] '{text}' | Conf: {conf:.3f} | Length: {len(text)}")

        avg_confidence = sum(conf for _, _, conf in test_results) / len(test_results)
        
        if len(test_results) == 0 or (len(test_results) == 1 and not test_results[0][1].strip()):
            return "empty"
        elif 0 < avg_confidence < 0.2:
            return "low_confidence"
        elif 0.2 <= avg_confidence < 0.8:
            return "medium_confidence"  
        elif avg_confidence >= 0.8:
            return "high_confidence"

    def preprocess_image(self, image_path: str) -> np.ndarray:
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")
        
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot load image: {image_path}")

        quality = self.detect_image_quality(image_path)
        
        
        if quality == "empty" or quality == "low_confidence":
            print("🔧 Low confidence image, using aggressive preprocessing")

            # # Aggressive preprocessing with threshold
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Enhance contract
            contrast = cv2.convertScaleAbs(gray, alpha=1.5, beta=1)

            # Denoise the image with Gaussian Blur
            blurred = cv2.GaussianBlur(contrast, (3, 3), 0)

            # Threshold the image (binary)
            _, threshold_img = cv2.threshold(blurred, 128, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Auto-invert
            black_pixels = np.sum(threshold_img == 0)
            total_pixels = threshold_img.size
            black_ratio = black_pixels / total_pixels
            
            if black_ratio > 0.75:
                return cv2.bitwise_not(threshold_img)
            else:
                return threshold_img
        else:
            print("🔧 Medium confidence image, using gentle preprocessing") 

            # Gentle preprocessing with CLAHE
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Auto-invert if text is white on black background
            mean_val = np.mean(gray)
            if mean_val < 127:
                gray = 255 - gray

            # Enhance contrast using CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # Denoise
            denoised = cv2.fastNlMeansDenoising(enhanced)
                    
            # Scale up if image is too small
            height, width = denoised.shape
            min_size = 800
                    
            if max(height, width) < min_size:
                scale = min_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                denoised = cv2.resize(
                    denoised, 
                    (new_width, new_height), 
                    interpolation=cv2.INTER_CUBIC
                )
            return denoised
    
    def contains_japanese(self, text: str) -> bool:
        japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\uFF66-\uFF9F\u3000-\u303F\uFF00-\uFFEF。、？！「」]')
        return bool(japanese_pattern.search(text))
    
    def filter_japanese_results(self, raw_results: List, min_confidence: float = 0.2) -> List[OCRResult]:
        filtered_results = []
        
        for bbox, text, confidence in raw_results:
            if confidence >= min_confidence:
                is_japanese = self.contains_japanese(text)
                
                result = OCRResult(
                    text=text.strip(),
                    confidence=confidence,
                    bbox=bbox,
                    is_japanese=is_japanese
                )
                filtered_results.append(result)
        
        return filtered_results
    
    def detect_single_character_image(self, image_path: str) -> bool:
        
        # Test without preprocessing
        result = self.reader.readtext(image_path, text_threshold=0.2)

        # One character only
        if len(result) == 1 and len(result[0][1]) == 1:
            return True
        return False

    def extract_results(self, image_path: str) -> List[OCRResult]:
        try:
            confidence = self.detect_image_quality(image_path)
            is_single_char = self.detect_single_character_image(image_path)

            if confidence=="high_confidence":
                print(f"🔍 High confidence detected, skipping preprocessing")
                results_standard = self.reader.readtext(image_path, text_threshold=0.2)
                print("Length: " + str(len(results_standard)))
            else:
                processed_img = self.preprocess_image(image_path)
                results_standard = self.reader.readtext(processed_img, text_threshold=0.2)
                print("Length after preprocessing: " + str(len(results_standard)))
        
                if is_single_char and confidence != "empty":
                    print("🔍 Single character detected, skipping preprocessing")
                    results_standard = self.reader.readtext(image_path, text_threshold=0.2)
                    print("Length: " + str(len(results_standard)))
            
                # If too little text is detected, try enhanced
                if (2 <= len(results_standard) <= 3) or len(results_standard) < 1: 
                    print("🔄 Few detections with standard: " + str(len(results_standard)) + ", trying enhanced...")
                    results_enhanced = self.reader.readtext(image_path, text_threshold=0.2, low_text=0.6)
                        
                    # Use enhance only if more text is detected
                    if len(results_enhanced) > len(results_standard):
                        print("✅ Enhanced detected more text, using enhanced")
                        print("Length after enhanced preprocessing: " + str(len(results_enhanced)))

                        print("🔍 DEBUG: Processed results before filtering:")
                        for i, (_, text, conf) in enumerate(results_enhanced):
                            print(f"  [{i}] '{text}' | Conf: {conf:.3f} | Length: {len(results_enhanced)}")

                        return self.filter_japanese_results(results_enhanced)
            
            # Debug raw results:
            print("🔍 DEBUG: Processed results before filtering:")
            for i, (_, text, conf) in enumerate(results_standard):
                print(f"  [{i}] '{text}' | Conf: {conf:.3f} | Length: {len(results_standard)}")
                
            print("✅ Using standard detection")
            filtered = self.filter_japanese_results(results_standard)

            if not filtered and len(results_standard) > 0:
                print("🔄 No results with standard confidence, trying lower threshold...")
                filtered = self.filter_japanese_results(results_standard, min_confidence=0.0)
                print(f"🔍 With lower threshold: {len(filtered)} results")
            
            return filtered    
           
        except Exception:
            return []
    
    
    def process_image(self, image_path: str) -> ProcessingResult:
        
        if not self.is_ready:
            return ProcessingResult(
                success=False,
                results=[],
                combined_text="",
                error_message="OCR engine not initialized"
            )
        
        if not os.path.exists(image_path):
            return ProcessingResult(
                success=False,
                results=[],
                combined_text="",
                error_message=f"Image file not found: {image_path}"
            )
        
        start_time = time.time()
        
        try:
            results = self.extract_results(image_path)
            
             # Filter for Japanese text
            japanese_results = [r for r in results if r.is_japanese]
            
            if not japanese_results:
                return ProcessingResult(
                    success=False,
                    results=[],
                    combined_text="",
                    error_message="No Japanese text detected",
                    processing_time=time.time() - start_time
                )
            # Combine text cleanly
            combined_text = "".join([r.text for r in japanese_results])
            
            processing_time = time.time() - start_time
            return ProcessingResult(
                success=True,
                results=japanese_results,
                combined_text=combined_text,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            return ProcessingResult(
                success=False,
                results=[],
                combined_text="",
                error_message=str(e),
                processing_time=processing_time
            )
    
    def translate_extracted_results(self, text, target_language: str) -> str:
        translator = Translator()
        result = translator.translate(text.strip(), src="ja", dest=target_language)

        return result.text
        