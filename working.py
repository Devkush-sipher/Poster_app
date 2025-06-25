import gradio as gr
from PIL import Image, ImageDraw, ImageFont
import os
import requests
import io

# --- New Function to Call Hugging Face Inference API ---
# This replaces the entire SimplePosterGenerator class.
def create_background_via_api(prompt: str, width: int, height: int, retries=3):
    """
    Generates a background image using the Hugging Face Inference API.
    """
    # Securely get the Hugging Face token from environment variables
    token = os.getenv("HF_TOKEN")
    if not token:
        print("❌ Hugging Face token not found. Please set the HF_TOKEN environment variable.")
        return create_fallback_background(width, height)

    model_id = "prompthero/openjourney"
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {token}"}

    full_prompt = f"{prompt}, poster design, concept art, trending on artstation, sharp, 4k, mdjrny-v4 style"

    # The API can sometimes be loading a model, so we add a retry mechanism
    for i in range(retries):
        try:
            response = requests.post(
                api_url,
                headers=headers,
                json={"inputs": full_prompt, "parameters": {"width": width, "height": height}},
                timeout=120 # Add a timeout for the request
            )

            if response.status_code == 200:
                print("✅ Background generated via API.")
                image_bytes = response.content
                return Image.open(io.BytesIO(image_bytes))
            elif response.status_code == 503: # Model is loading
                print(f"⏳ Model is loading, attempt {i+1}/{retries}. Retrying...")
                time.sleep(15) # Wait for 15 seconds before retrying
                continue
            else:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                break # Exit loop on other errors
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            break

    print("❗️ API failed after retries, creating a fallback background.")
    return create_fallback_background(width, height)


# --- Helper functions from your original code (mostly unchanged) ---

def create_fallback_background(width, height):
    colors = [(100, 150, 255), (150, 200, 255)]
    return create_gradient_background(width, height, colors[0], colors[1])

def create_gradient_background(width, height, color1, color2):
    image = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return image

def get_font(size):
    try:
        # These fonts are commonly available on Linux systems used by Vercel
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except IOError:
        print("Default font not found, loading fallback.")
        return ImageFont.load_default()

def process_logo(logo_image, max_size=200):
    if logo_image is None:
        return None
    try:
        logo = logo_image.copy()
        logo.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        return logo
    except Exception as e:
        print(f"Logo processing error: {e}")
        return None

def draw_text_with_outline(draw, text, x, y, font, fill_color, outline_color, center=False):
    if center:
        try:
            # Use textbbox for more accurate centering
            bbox = draw.textbbox((0, 0), text, font=font)
            x -= (bbox[2] - bbox[0]) // 2
        except AttributeError: # Fallback for older Pillow versions
            w, h = draw.textsize(text, font=font)
            x -= w // 2

    # Outline
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    # Fill
    draw.text((x, y), text, font=font, fill=fill_color)

def apply_text_layout(image, subtitle, details, logo=None):
    poster = image.copy().convert('RGBA')
    width, height = poster.size
    overlay = Image.new('RGBA', poster.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Darkening overlay for better text visibility
    color_overlay = Image.new('RGBA', poster.size, (0, 0, 0, 80))
    poster = Image.alpha_composite(poster, color_overlay)

    base_size = min(width, height) // 15
    subtitle_size = int(base_size * 0.8)
    details_size = int(base_size * 0.5)

    subtitle_font = get_font(subtitle_size)
    details_font = get_font(details_size)

    y_pos = height // 3
    spacing = int(base_size * 1.2) # Dynamic spacing

    if subtitle:
        draw_text_with_outline(draw, subtitle, width//2, y_pos, subtitle_font, 'white', 'black', center=True)
        y_pos += spacing

    if details:
        details_lines = [line.strip() for line in details.split('\n') if line.strip()]
        for i, line in enumerate(details_lines):
            draw_text_with_outline(draw, line, width//2, y_pos, details_font, 'lightgray', 'black', center=True)
            y_pos += int(details_size * 1.5)

    if logo:
        logo_pos = (width - logo.size[0] - 40, 40)
        poster.paste(logo, logo_pos, logo)

    final_poster = Image.alpha_composite(poster, overlay)
    return final_poster.convert('RGB')


# --- Main Gradio Function (Modified) ---
def generate_simple_poster(prompt, subtitle, details, logo_image, aspect_ratio):
    aspect_ratios = {
        "1:1 - Square": (1024, 1024),
        "2:3 - Portrait": (683, 1024),
        "3:2 - Landscape": (1024, 683),
        "3:4 - Poster": (768, 1024),
        "16:9 - Widescreen": (1024, 576)
    }
    width, height = aspect_ratios.get(aspect_ratio, (1024, 1024))

    # MODIFIED: Call the new API function
    background = create_background_via_api(prompt, width, height)

    processed_logo = process_logo(logo_image)
    final_poster = apply_text_layout(background, subtitle, details, processed_logo)
    return final_poster


# --- Gradio Interface (Unchanged) ---
def create_simple_interface():
    with gr.Blocks(title="🎨 Simple AI Poster Generator", theme=gr.themes.Glass()) as demo:
        gr.HTML("""
        <div style="text-align: center; padding: 20px;">
            <h1 style="font-size: 3em; background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1);
                        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                        background-clip: text; margin-bottom: 10px;">
                🎨 Simple AI Poster Generator
            </h1>
            <p style="font-size: 1.2em; color: #666;">
                Create stunning posters with the OpenJourney fine-tuned model!
            </p>
        </div>
        """)
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 🎯 Poster Description")
                    prompt_input = gr.Textbox(
                        label="Describe your poster",
                        value="Tech conference poster with futuristic cityscape",
                        lines=3
                    )

                with gr.Group():
                    gr.Markdown("### 📝 Text Content")
                    subtitle_input = gr.Textbox(label="Subtitle", value="Tech Summit 2024")
                    details_input = gr.Textbox(
                        label="Details",
                        value="December 15-17, 2024\nConvention Center\nRegister: techsummit.com",
                        lines=4
                    )

                with gr.Group():
                    gr.Markdown("### 🖼 Optional Logo")
                    logo_upload = gr.Image(label="Upload Logo (Optional)", type="pil", height=150)

                with gr.Group():
                    gr.Markdown("### 📐 Output Settings")
                    aspect_ratio_radio = gr.Radio(
                        choices=["1:1 - Square", "2:3 - Portrait", "3:2 - Landscape", "3:4 - Poster", "16:9 - Widescreen"],
                        value="3:4 - Poster",
                        label="Aspect Ratio"
                    )
                    generate_btn = gr.Button("🚀 Generate Poster", variant="primary", size="lg")

            with gr.Column(scale=2):
                gr.Markdown("### ✨ Generated Poster")
                output_image = gr.Image(label="Your AI-Generated Poster", type="pil", interactive=False)

        generate_btn.click(
            generate_simple_poster,
            inputs=[prompt_input, subtitle_input, details_input, logo_upload, aspect_ratio_radio],
            outputs=[output_image],
            api_name="generate_poster"
        )
    return demo

# --- Run the App ---
# This part is important for Vercel to find and run the Gradio app.
demo = create_simple_interface()
# You can still use `demo.launch()` for local testing.
if __name__ == "__main__":
    demo.launch(debug=True)