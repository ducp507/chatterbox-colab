"""
Script -> per-scene English image-generation prompts, via the official
Gemini API (google-genai). Same rule set saved for Phương's video pipeline
(character references handle appearance; Gemini only writes action/camera/
setting per 8s scene), run as one chat session so the model keeps track of
scene numbering and script coverage across batched requests -- matching how
this was done by hand in AI Studio (30 prompts per turn, don't repeat,
don't skip).

Needs a Gemini API key (free, from aistudio.google.com/apikey). Text
generation is on Gemini's free tier, so this costs nothing to run.
"""
import os
import re

# Same rule set as saved in Claude's memory (scene-image-prompt-rules.md),
# minus the fixed "~150 scenes" framing -- the actual target count is a
# runtime parameter here (video length / 8s, or a manual override).
SCENE_PROMPT_RULES = """TẤT CẢ BỐI CẢNH VÀ NHÂN VẬT ĐƯỢC THÊM VÀO TRONG PROMPT ĐỀU PHẢI LÀ NGƯỜI CHÂU Á.

Từ kịch bản dưới đây, liệt kê chi tiết từng phân cảnh.

1. Cấu trúc phân cảnh
Mỗi phân cảnh bắt buộc gồm đúng 1 prompt. Không gộp hoặc chia thiếu số lượng prompt.

2. Tính độc lập của prompt
Mỗi prompt phải độc lập hoàn toàn, không được xem là tiếp nối prompt trước.
Trong mỗi prompt phải nêu lại bối cảnh chung.
Không dùng "tiếp tục", "vẫn", "lúc này", "sau đó", "như trước".

3. Bối cảnh lặp lại
Đọc toàn bộ script để xác định những địa điểm/không gian nào xuất hiện
từ 2 cảnh trở lên. Với mỗi bối cảnh lặp lại, mô tả nhất quán y hệt nhau
(chất liệu, hình dạng, cách bố trí) ở lần xuất hiện đầu tiên, và giữ
nguyên mô tả đó mỗi lần bối cảnh đó xuất hiện lại. Bối cảnh chỉ xuất
hiện 1 lần thì mô tả tự do theo đúng nội dung script tại cảnh đó.

4. Nhân vật
Tất cả nhân vật đều đã có sẵn ảnh tham chiếu riêng (do người dùng cung
cấp khi tạo ảnh) — vì vậy trong MỌI prompt, chỉ gọi tên nhân vật đúng
theo tên trong script, TUYỆT ĐỐI KHÔNG mô tả ngoại hình, trang phục,
dáng người. Prompt chỉ tập trung mô tả hành động, cử chỉ, vị trí và
tương tác của nhân vật đó trong khung hình.

5. Nhân vật & số lượng
Mỗi prompt bắt buộc ghi rõ số lượng nhân vật xuất hiện trong khung hình.
Số lượng thay đổi linh hoạt theo logic kịch bản, không cố định, không tùy tiện.
Nếu ghi "X nhân vật": bắt buộc mô tả hành động của tất cả X nhân vật,
không được để nhân vật đứng cho đủ số.

6. Hành động & cử chỉ
Nhân vật không được đứng yên, không nhìn vô định.
Bắt buộc mô tả: hành động cụ thể, cử chỉ tay, hướng thân người / tương tác không gian.
Tránh cảm giác "ảnh thờ", "tạo dáng chụp hình".

7. Góc quay & phong cách
Thay đổi góc quay linh hoạt theo phong cách điện ảnh: toàn cảnh, trung cảnh,
góc thấp / góc lệch / nhìn qua vật cản. Không lặp góc máy nhàm chán giữa các prompt.

8. Nội dung bị cấm đề cập
Không đề cập ánh sáng (ánh nắng, ánh đèn, sáng – tối…).
Không đề cập thời gian (sáng, chiều, tối, hoàng hôn…).
Không mô tả cảm xúc trừu tượng nếu không gắn với hành động cụ thể.

9. Trọng tâm mô tả
Chỉ tập trung vào: hành động, cử chỉ, tương tác nhân vật – không gian.
Mỗi prompt nên thể hiện một khoảnh khắc có chuyển động rõ ràng.

10. Phong cách hình ảnh cố định
Cuối MỖI prompt, thêm nguyên văn dòng sau (giữ y hệt, không đổi):
"Visual style: cinematic realistic photography, natural color grading,
shallow depth of field, consistent film-like tone, high detail,
no text, no watermark, no logo."

11. Ngôn ngữ output
Toàn bộ nội dung prompt (mô tả bối cảnh, nhân vật, hành động) phải viết
bằng TIẾNG ANH — kể cả khi kịch bản gốc là tiếng Việt.

Lưu ý quan trọng: tất cả các phân cảnh phải được tạo LẦN LƯỢT theo đúng
tuyến nội dung của kịch bản, không được lẫn lộn đầu đuôi, không được lặp
lại phân cảnh. Toàn bộ nội dung kịch bản phải được trải đều xuyên suốt
đúng {target_n} phân cảnh.

Định dạng bắt buộc cho MỖI prompt: một dòng riêng, bắt đầu bằng số thứ
tự và dấu chấm, ví dụ:
1. [nội dung prompt tiếng Anh]
2. [nội dung prompt tiếng Anh]
Không thêm bất kỳ lời giải thích, tiêu đề, hay ghi chú nào khác ngoài các
dòng prompt đã đánh số."""

BATCH_SIZE = 30
_NUM_LINE_RE = re.compile(r"^\s*(\d+)\.\s*(.+)$")


def _parse_numbered_lines(text):
    """Pull out {number: prompt_text} pairs from a model response, tolerant
    of the model wrapping a long prompt across multiple physical lines."""
    out = {}
    current_num = None
    for line in text.splitlines():
        m = _NUM_LINE_RE.match(line)
        if m:
            current_num = int(m.group(1))
            out[current_num] = m.group(2).strip()
        elif current_num is not None and line.strip():
            out[current_num] = (out[current_num] + " " + line.strip()).strip()
    return out


def generate_scene_prompts(full_script, script_file, video_length_s, num_scenes_override, api_key):
    """Generator: yields (progress_0_100, status_text, file_path_or_None).
    file_path is only set on the final yield, pointing at a .txt with all
    numbered prompts (one per line) for easy pasting into Flow."""
    try:
        if script_file:
            from .generation_functions import _extract_script_lines
            lines = _extract_script_lines(None, script_file)
            full_script = "\n".join(lines)

        if not full_script or not full_script.strip():
            yield 0, "❌ Error: No script found. Paste a script or upload a .txt/.csv/.xlsx file.", None
            return

        key = (api_key or "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            yield 0, ("❌ Error: No Gemini API key. Get a free one at "
                       "aistudio.google.com/apikey and paste it in, or set "
                       "the GEMINI_API_KEY env var / Colab secret."), None
            return

        target_n = int(num_scenes_override) if num_scenes_override else max(1, round(float(video_length_s or 0) / 8))
        if target_n < 1:
            yield 0, "❌ Error: Need at least 1 scene (check video length / scene count).", None
            return

        try:
            from google import genai
        except ImportError:
            yield 0, "❌ Error: google-genai isn't installed. Run: pip install google-genai", None
            return

        client = genai.Client(api_key=key)
        chat = client.chats.create(model="gemini-2.5-flash")

        rules = SCENE_PROMPT_RULES.format(target_n=target_n)
        first_message = (
            f"{rules}\n\n"
            f"KỊCH BẢN:\n{full_script}\n\n"
            f"Bắt đầu viết {min(BATCH_SIZE, target_n)} prompt đầu tiên "
            f"(phân cảnh 1 đến {min(BATCH_SIZE, target_n)} trong tổng số {target_n})."
        )

        yield 3, f"Sending script to Gemini... (target: {target_n} scenes, {target_n} / 8 = ~{target_n * 8 / 60:.1f} min video)", None
        all_prompts = {}
        scene_idx = 1
        message = first_message
        while scene_idx <= target_n:
            batch_end = min(scene_idx + BATCH_SIZE - 1, target_n)
            progress = 3 + int((scene_idx / target_n) * 90)
            yield progress, f"Generating scenes {scene_idx}-{batch_end} of {target_n}...", None

            response = chat.send_message(message)
            batch = _parse_numbered_lines(response.text or "")
            all_prompts.update(batch)

            got = sorted(k for k in batch if scene_idx <= k <= batch_end)
            if not got:
                yield 0, (
                    f"❌ Error: Gemini's reply for scenes {scene_idx}-{batch_end} didn't "
                    f"parse as numbered lines. Raw reply:\n\n{(response.text or '')[:2000]}"
                ), None
                return

            scene_idx = batch_end + 1
            next_end = min(scene_idx + BATCH_SIZE - 1, target_n)
            if scene_idx <= target_n:
                message = (
                    f"Tiếp tục viết prompt {scene_idx} đến {next_end} "
                    f"(trong tổng số {target_n}), đúng format đã yêu cầu, "
                    f"không lặp lại nội dung đã viết."
                )

        lines = [f"{i}. {all_prompts.get(i, '⚠️ MISSING')}" for i in range(1, target_n + 1)]
        missing = [i for i in range(1, target_n + 1) if i not in all_prompts]
        full_text = "\n".join(lines)

        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="scene_prompts_")
        out_path = os.path.join(tmp_dir, "scene_prompts.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        status = f"✅ Done! {target_n} scene prompts generated."
        if missing:
            status += f"\n⚠️ {len(missing)} scene(s) missing/unparsed: {missing[:20]}{'...' if len(missing) > 20 else ''}"
        yield 100, status + "\n\n" + full_text, out_path

    except Exception as e:
        yield 0, f"❌ Error: {str(e)}", None
