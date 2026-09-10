"""
UI Components for Chatterbox TTS Enhanced
Contains function to create each tab's UI layout
"""
import gradio as gr
from .config import LANGUAGE_CONFIG, SUPPORTED_LANGUAGES
from .voice_manager import load_voices, get_voices_for_language, get_all_voices_with_gender


def create_header():
    """Create the application header."""
    gr.HTML("""
        <h1 style="font-size: 2.5em; margin-bottom: 0.5rem; text-align: center;">⚡ Chatterbox Turbo TTS (Supports 23 Languages) </h1>
        <p style='text-align: center; font-size: 1.2em; color: #666;'>High-Quality Voice Cloning, Text-to-Speech & Voice Conversion</p>
        
        <!-- Channel Section -->
        <div style="display: flex; justify-content: center; align-items: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); 
                    margin: 1.5rem auto; max-width: 700px;">
            <div style="display: flex; align-items: center; gap: 1.5rem; width: 100%;">
                      <img src="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAkACQAAD/4QMCRXhpZgAATU0AKgAAAAgACAESAAMAAAABAAEAAAMBAAUAAAABAAABegMDAAEAAAABAAAAAFEQAAEAAAABAQAAAFERAAQAAAABAAAWJVESAAQAAAABAAAWJYdpAAQAAAABAAABguocAAcAAAEMAAAAbgAAAAAc6gAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGGoAAAsY8ABZADAAIAAAAUAAAC0JAEAAIAAAAUAAAC5JKRAAIAAAADMDAAAJKSAAIAAAADMDAAAOocAAcAAAEMAAABxAAAAAAc6gAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMjAyNToxMjowNiAwNjo1Njo1NwAyMDI1OjEyOjA2IDA2OjU2OjU3AAAA/+ECrGh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8APD94cGFja2V0IGJlZ2luPSfvu78nIGlkPSdXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQnPz4NCjx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iPjxyZGY6UkRGIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyI+PHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9InV1aWQ6ZmFmNWJkZDUtYmEzZC0xMWRhLWFkMzEtZDMzZDc1MTgyZjFiIiB4bWxuczpleGlmPSJodHRwOi8vbnMuYWRvYmUuY29tL2V4aWYvMS4wLyI+PGV4aWY6RGF0ZVRpbWVPcmlnaW5hbD4yMDI1LTEyLTA2VDA2OjU2OjU3PC9leGlmOkRhdGVUaW1lT3JpZ2luYWw+PC9yZGY6RGVzY3JpcHRpb24+PC9yZGY6UkRGPjwveDp4bXBtZXRhPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDw/eHBhY2tldCBlbmQ9J3cnPz7/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBwcGBwcICQsJCAgKCAcHCg0KCgsMDAwMBwkODw0MDgsMDAz/2wBDAQICAgMDAwYDAwYMCAcIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAARCADuAS8DASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm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" alt="Channel Logo" style="width: 60px; height: 60px; border-radius: 50%; border: 2px solid #ccc; object-fit: cover;">

            <div style="text-align: left; flex-grow: 1; color: white;">
                <h3 style="margin: 0; font-size: 1.5rem; font-weight: 600;">Chatterbox by The Oracle Guy</h3>
                <p style="font-size: 1rem; margin-top: 0.5rem; opacity: 0.9;">Subscribe for more such future releases!</p>
            </div>
            <!-- Subscribe Button -->
            <a href="https://www.youtube.com/@theoracleguy_AI?sub_confirmation=1" target="_blank"
                style="background-color: #E74C3C; color: white; padding: 10px 20px; font-size: 1.1rem;
                        text-decoration: none; border-radius: 4px; font-weight: 600; display: inline-flex;
                        align-items: center; gap: 12px; box-shadow: 0 4px 8px rgba(255, 0, 0, 0.2);
                        transition: background-color 0.3s, box-shadow 0.3s;">
                Subscribe
            </a>
        </div>
    </div>
    """)


def create_tts_tab():
    """Create the UI for Text-to-Speech tab."""
    with gr.Row():
        with gr.Column():
            text = gr.Textbox(
                value="Hey there! I'm The Oracle Guy, and I'm unlocking the secrets of AI!",
                label="Text to synthesize (unlimited length - smart chunking enabled)",
                max_lines=10,
                placeholder="Enter text to convert to speech..."
            )
            
            voice_select_tts = gr.Dropdown(
                label="Select Voice",
                choices=get_voices_for_language("en"),
                value=f"Default ({SUPPORTED_LANGUAGES['en']})",
                info="Select a cloned voice or use default"
            )
            
            preview_audio_tts = gr.Audio(label="Voice Preview", interactive=False, visible=True)
            
            gr.Markdown("**Language:** English only for this tab. Use Multilingual TTS for other languages.")
            
            exaggeration = gr.Slider(0.25, 2, step=.05, label="Exaggeration (Neutral = 0.5)", value=.5)
            cfg_weight = gr.Slider(0.0, 1, step=.05, label="CFG/Pace", value=0.5)

            with gr.Accordion("⚙️ Advanced Options", open=False):
                seed_num = gr.Number(value=0, label="Random seed (0 for random)")
                temp = gr.Slider(0.05, 5, step=.05, label="Temperature", value=.8)
                min_p = gr.Slider(0.00, 1.00, step=0.01, label="min_p (0.00 disables)", value=0.05)
                top_p = gr.Slider(0.00, 1.00, step=0.01, label="top_p (1.0 disables)", value=1.00)
                repetition_penalty = gr.Slider(1.00, 2.00, step=0.1, label="Repetition Penalty", value=1.2)

            generate_btn = gr.Button("🎙️ Generate Speech", variant="primary", size="lg")

        with gr.Column():
            progress_bar_tts = gr.Slider(label="Progress", minimum=0, maximum=100, value=0, interactive=False)
            status_box_tts = gr.Textbox(label="Status", value="Ready to generate...", lines=3, interactive=False)
            audio_output_tts = gr.Audio(label="Generated Audio", autoplay=True, show_download_button=True)

    return {
        "text": text,
        "voice_select": voice_select_tts,
        "exaggeration": exaggeration,
        "cfg_weight": cfg_weight,
        "seed_num": seed_num,
        "temp": temp,
        "min_p": min_p,
        "top_p": top_p,
        "repetition_penalty": repetition_penalty,
        "generate_btn": generate_btn,
        "progress_bar": progress_bar_tts,
        "status_box": status_box_tts,
        "audio_output": audio_output_tts,
        "preview_audio": preview_audio_tts
    }


def create_multilingual_tab():
    """Create the UI for Multilingual TTS tab."""
    with gr.Row():
        with gr.Column():
            text_mtl = gr.Textbox(
                value=LANGUAGE_CONFIG["fr"]["text"],
                label="Text to synthesize (unlimited length - smart chunking enabled)",
                max_lines=5,
                placeholder="Enter text in any supported language..."
            )
            
            language_select_mtl = gr.Dropdown(
                label="Language",
                choices=[(f"{name} ({code})", code) for code, name in sorted(SUPPORTED_LANGUAGES.items())],
                value="fr",
                info="Select the language of your text"
            )
            
            voice_select_mtl = gr.Dropdown(
                label="Select Voice",
                choices=get_voices_for_language("fr"),
                value=f"Default ({SUPPORTED_LANGUAGES['fr']})",
                info="Select a voice for this language"
            )
            
            sample_audio_mtl = gr.Audio(
                label="Voice Preview",
                value=LANGUAGE_CONFIG["fr"]["audio"],
                interactive=False
            )
            
            exaggeration_mtl = gr.Slider(0.25, 2, step=.05, label="Exaggeration (Neutral = 0.5)", value=.5)
            cfg_weight_mtl = gr.Slider(0.0, 1, step=.05, label="CFG/Pace", value=0.5)

            with gr.Accordion("⚙️ Advanced Options", open=False):
                seed_num_mtl = gr.Number(value=0, label="Random seed (0 for random)")
                temp_mtl = gr.Slider(0.05, 5, step=.05, label="Temperature", value=.8)

            generate_btn_mtl = gr.Button("🎙️ Generate Speech", variant="primary", size="lg")

        with gr.Column():
            progress_bar_mtl = gr.Slider(label="Progress", minimum=0, maximum=100, value=0, interactive=False)
            status_box_mtl = gr.Textbox(label="Status", value="Ready to generate...", lines=3, interactive=False)
            audio_output_mtl = gr.Audio(label="Generated Audio", autoplay=True, show_download_button=True)
            
            gr.Markdown(f"""
            ### Supported Languages ({len(SUPPORTED_LANGUAGES)}):
            {', '.join([f"**{name}**" for name in sorted(SUPPORTED_LANGUAGES.values())])}
            """)

    return {
        "text": text_mtl,
        "language_select": language_select_mtl,
        "voice_select": voice_select_mtl,
        "sample_audio": sample_audio_mtl,
        "exaggeration": exaggeration_mtl,
        "cfg_weight": cfg_weight_mtl,
        "seed_num": seed_num_mtl,
        "temp": temp_mtl,
        "generate_btn": generate_btn_mtl,
        "progress_bar": progress_bar_mtl,
        "status_box": status_box_mtl,
        "audio_output": audio_output_mtl
    }


def create_voice_conversion_tab():
    """Create the UI for Voice Conversion tab."""
    with gr.Row():
        with gr.Column():
            gr.Markdown("""
            ### Convert any voice to another!
            Upload an audio file and select a target voice to convert it.
            """)
            
            input_audio_vc = gr.Audio(
                label="Input Audio",
                sources=["upload", "microphone"],
                type="filepath"
            )
            
            target_voice_select = gr.Dropdown(
                label="Target Voice",
                choices=["None"] + get_all_voices_with_gender(),
                value="None",
                info="Select target voice or use default"
            )
            
            preview_audio_vc = gr.Audio(label="Target Voice Preview", interactive=False, visible=True)
            
            convert_btn = gr.Button("🔄 Convert Voice", variant="primary", size="lg")

        with gr.Column():
            progress_bar_vc = gr.Slider(label="Progress", minimum=0, maximum=100, value=0, interactive=False)
            status_box_vc = gr.Textbox(label="Status", value="Ready to convert...", lines=3, interactive=False)
            audio_output_vc = gr.Audio(label="Converted Audio", autoplay=True, show_download_button=True)

    return {
        "input_audio": input_audio_vc,
        "target_voice_select": target_voice_select,
        "preview_audio": preview_audio_vc,
        "convert_btn": convert_btn,
        "progress_bar": progress_bar_vc,
        "status_box": status_box_vc,
        "audio_output": audio_output_vc
    }


def create_clone_voice_tab():
    """Create the UI for Clone Voice tab."""
    with gr.Row():
        with gr.Column():
            gr.Markdown("""
            ### Clone any voice instantly!
            
            **How to clone:**
            1. Upload or record a clear audio sample (5-30 seconds)
            2. Name your voice and select gender
            3. Select the language
            4. Click "Clone Voice"
            5. Use it in any tab!
            
            **Tips for best results:**
            - Use clear, high-quality audio
            - Avoid background noise
            - 10-20 seconds is ideal
            - Multiple sentences work better
            """)
            
            new_voice_name = gr.Textbox(
                label="Voice Name",
                placeholder="e.g., Amitabh, Priyanka, Morgan..."
            )
            
            voice_gender = gr.Radio(
                label="Gender",
                choices=[("Male ♂️", "male"), ("Female ♀️", "female")],
                value="male",
                info="Select the gender for display purposes"
            )
            
            voice_language = gr.Dropdown(
                label="Voice Language",
                choices=[(f"{name} ({code})", code) for code, name in sorted(SUPPORTED_LANGUAGES.items())],
                value="en",
                info="Select the language of the voice sample"
            )
            
            ref_audio_input = gr.Audio(
                label="Reference Audio Sample",
                sources=["upload", "microphone"],
                type="filepath"
            )
            clone_btn = gr.Button("🧬 Clone Voice", variant="primary", size="lg")
            
        with gr.Column():
            clone_status = gr.Textbox(label="Cloning Status", lines=3)
            gr.Markdown("""
            ### Your Cloned Voices:
            After cloning, your voice will appear in all tabs.
            
            **Voice Storage:**
            - Saved in `voice_samples` folder
            - Manage from this tab
            - Delete when no longer needed
            
            **Current Voices:**
            """)
            
            # Load current voices for initial display
            current_voices = load_voices()
            voices_display_text = "\n".join(current_voices) if current_voices else "No voices cloned yet"
            
            current_voices_display = gr.Textbox(
                value=voices_display_text,
                label="Cloned Voices",
                lines=5,
                interactive=False
            )
            
            with gr.Row():
                voice_to_delete = gr.Dropdown(
                    label="Select Voice to Delete",
                    choices=["None"] + current_voices,
                    value="None",
                    info="Select a cloned voice to delete"
                )
                delete_btn_clone = gr.Button("🗑️ Delete Voice", variant="secondary", size="sm")
            
            delete_status_clone = gr.Textbox(label="Delete Status", lines=2)

    return {
        "new_voice_name": new_voice_name,
        "voice_gender": voice_gender,
        "voice_language": voice_language,
        "ref_audio_input": ref_audio_input,
        "clone_btn": clone_btn,
        "clone_status": clone_status,
        "current_voices_display": current_voices_display,
        "voice_to_delete": voice_to_delete,
        "delete_btn": delete_btn_clone,
        "delete_status": delete_status_clone
    }


def create_turbo_tab():
    """Create the UI for Turbo TTS tab."""
    with gr.Row():
        with gr.Column():
            gr.Markdown("""
            ### ⚡ Chatterbox-Turbo - Ultra-Fast TTS
            
            **What's New:**
            - **350M parameters** - Streamlined architecture
            - **10x faster** - One-step decoder (vs 10 steps)
            - **Native paralinguistic tags** - Add realistic emotions!
            - **Low-latency** - Perfect for voice agents
            
            **Available Paralinguistic Tags:**
            `[clear throat]` `[sigh]` `[shush]` `[cough]` `[groan]` 
            `[sniff]` `[gasp]` `[chuckle]` `[laugh]`
            
            **Example:**
            *"Hi there, Sarah here from MochaFone calling you back [chuckle], have you got one minute to chat about the billing issue?"*
            """)
            
            text_turbo = gr.Textbox(
                value="Hi there! [chuckle] I'm The Oracle Guy, and I'm unlocking the secrets of AI with Chatterbox-Turbo!",
                label="Text to synthesize (unlimited length - smart chunking enabled)",
                max_lines=5,
                placeholder="Enter text with optional paralinguistic tags like [chuckle], [laugh], [sigh]...",
                elem_id="turbo_textbox"
            )
            
            # Paralinguistic tag buttons with custom styling
            gr.Markdown("**Quick Insert Tags:**")
            with gr.Row(elem_classes="tag-container"):
                btn_clear_throat = gr.Button("[clear throat]", size="sm", elem_classes="tag-btn")
                btn_sigh = gr.Button("[sigh]", size="sm", elem_classes="tag-btn")
                btn_shush = gr.Button("[shush]", size="sm", elem_classes="tag-btn")
                btn_cough = gr.Button("[cough]", size="sm", elem_classes="tag-btn")
                btn_groan = gr.Button("[groan]", size="sm", elem_classes="tag-btn")
            
            with gr.Row(elem_classes="tag-container"):
                btn_sniff = gr.Button("[sniff]", size="sm", elem_classes="tag-btn")
                btn_gasp = gr.Button("[gasp]", size="sm", elem_classes="tag-btn")
                btn_chuckle = gr.Button("[chuckle]", size="sm", elem_classes="tag-btn")
                btn_laugh = gr.Button("[laugh]", size="sm", elem_classes="tag-btn")
            
            voice_select_turbo = gr.Dropdown(
                label="Select Voice (Required for Turbo)",
                choices=get_voices_for_language("en"),
                value=f"Default ({SUPPORTED_LANGUAGES['en']})",
                info="Turbo requires a reference voice clip for cloning"
            )
            
            preview_audio_turbo = gr.Audio(label="Voice Preview", interactive=False, visible=True)
            
            gr.Markdown("**Language:** English only. **Note:** Turbo model requires a voice reference.")

            
            generate_btn_turbo = gr.Button("⚡ Generate Speech (Turbo)", variant="primary", size="lg")

        with gr.Column():
            progress_bar_turbo = gr.Slider(label="Progress", minimum=0, maximum=100, value=0, interactive=False)
            status_box_turbo = gr.Textbox(label="Status", value="Ready to generate...", lines=3, interactive=False)
            audio_output_turbo = gr.Audio(label="Generated Audio", autoplay=True, show_download_button=True)
            
            gr.Markdown("""
            ### 💡 Tips for Best Results:
            - Use paralinguistic tags naturally in your text
            - Tags work best mid-sentence or at natural pauses
            - Combine multiple tags for complex emotions
            - Perfect for narration, voice agents, and creative workflows
            - Generation is ~3x faster than standard model
            """)

    return {
        "text": text_turbo,
        "voice_select": voice_select_turbo,
        "preview_audio": preview_audio_turbo,
        "generate_btn": generate_btn_turbo,
        "progress_bar": progress_bar_turbo,
        "status_box": status_box_turbo,
        "audio_output": audio_output_turbo,
        "btn_clear_throat": btn_clear_throat,
        "btn_sigh": btn_sigh,
        "btn_shush": btn_shush,
        "btn_cough": btn_cough,
        "btn_groan": btn_groan,
        "btn_sniff": btn_sniff,
        "btn_gasp": btn_gasp,
        "btn_chuckle": btn_chuckle,
        "btn_laugh": btn_laugh
    }

