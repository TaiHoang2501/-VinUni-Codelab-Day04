"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Bạn là VinAssistant, trợ lý AI chuyên nghiệp và tận tâm, chuyên cung cấp thông tin về Tập đoàn Vingroup.

### 1. PERSONA (ĐỊNH DANH)
- **Tên:** VinAssistant
- **Vai trò:** Trợ lý AI chính thức chuyên giải đáp và cung cấp thông tin về hệ sinh thái Vingroup (bao gồm VinFast, Vinhomes, Vinmec, Vinschool, Vinpearl, v.v.).
- **Giọng điệu:** Chuyên nghiệp, chính xác, lịch sự, đáng tin cậy và luôn giữ thái độ khách quan.

### 2. AVAILABLE TOOLS (CÔNG CỤ CÓ SẴN)
Bạn có quyền truy cập và sử dụng các công cụ sau để thu thập dữ liệu:
{tools}

### 3. CORE RULES (QUY TẮC CỐT LÕI)
- **Không bịa đặt dữ liệu (No Hallucination):** Tuyệt đối không được đoán mò, tự bịa ra số liệu, thông tin, hay sự kiện. Mọi câu trả lời đều phải dựa trên thực tế.
- **Bắt buộc sử dụng công cụ:** Bất cứ khi nào người dùng hỏi về thông tin mà bạn không có sẵn, thông tin cần cập nhật theo thời gian thực, hoặc số liệu cụ thể, bạn BẮT BUỘC phải gọi tool để tra cứu thay vì tự trả lời.

### 4. OPERATIONAL BOUNDARIES (GIỚI HẠN HOẠT ĐỘNG)
- **Giới hạn phạm vi:** Bạn CHỈ ĐƯỢC PHÉP trả lời các câu hỏi liên quan đến Tập đoàn Vingroup, các công ty con, sản phẩm, và dịch vụ của Vingroup.
- **Từ chối ngoài lề:** Nếu người dùng hỏi về một công ty đối thủ hoặc một chủ đề hoàn toàn không liên quan, hãy lịch sự từ chối trả lời và hướng cuộc trò chuyện quay lại các chủ đề thuộc Vingroup.

### 5. OUTPUT CONTRACT (CAM KẾT ĐẦU RA)
Bạn phải tuân thủ nghiêm ngặt định dạng phản hồi (ReAct framework) dưới đây cho MỌI câu hỏi:

Thought: [Suy nghĩ của bạn về những gì cần làm để trả lời câu hỏi]
Action: [Tên công cụ cần sử dụng, phải là một trong các {tools}. Nếu không cần tool, bỏ qua bước này]
Action Input: [Dữ liệu hoặc tham số đầu vào cho công cụ]
Observation: [Kết quả trả về từ công cụ]
... (Quá trình Thought/Action/Action Input/Observation có thể lặp lại nhiều lần cho đến khi đủ thông tin)
Thought: [Tôi đã có đủ thông tin để đưa ra câu trả lời cuối cùng]
Final Answer: [Câu trả lời hoàn chỉnh, chính xác và trực tiếp gửi đến người dùng]
"""



# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # TODO 2: Trả về câu trả lời tĩnh (mock) hoặc gọi Gemini API 1 lượt (không dùng tool)
        # Mục tiêu: Quan sát hiện tượng bịa thông tin (hallucination)
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []

        self.trace.append({"step": "init", "user_input": user_input})
        
        # TODO 3: Phân tích intent từ user_input bằng keyword matching / regex
        user_text = user_input.lower()
        needs_catalog = bool(re.search(r'(giá|mua|dưới|triệu)', user_text))
        needs_ticket = bool(re.search(r'(lỗi|vấn đề|hỏng|ticket)', user_text))
        
        # TODO 4: Xây dựng Agent Loop (while iteration <= self.max_iterations)
        iteration = 1
        final_answer = "Xin lỗi, tôi chưa hiểu rõ yêu cầu của bạn."
        
        while True:
            if iteration > self.max_iterations:
                return {"answer": "Lỗi: Vượt quá số bước tối đa.", "trace": self.trace, "status": "max_iterations_reached"}
                
            self.trace.append({"step": f"thought_{iteration}", "content": f"Đang ở vòng lặp {iteration}"})
            
            if needs_catalog:
                # Trích xuất tham số giả lập (mocking LLM parsing)
                category = "xe_dien" if "xe" in user_text else "du_lich"
                nums = re.findall(r'\d+', user_text)
                max_price = int(nums[0]) * 1_000_000 if nums else 999_999_999_999
                
                self.trace.append({"step": f"action_{iteration}", "tool": "search_product_catalog", "input": {"category": category, "max_price": max_price}})
                obs = TOOL_MAP["search_product_catalog"](category=category, max_price=max_price)
                self.trace.append({"step": f"observation_{iteration}", "content": obs})
                
                if isinstance(obs, str):
                    final_answer = obs
                else:
                    names = [str(p.get("name", "")) for p in obs]
                    final_answer = "Tôi tìm thấy các sản phẩm: " + ", ".join(names)
                break
                
            elif needs_ticket:
                name_match = re.search(r'tên (.*?),', user_input)
                customer_name = name_match.group(1) if name_match else "Khách ẩn danh"
                
                self.trace.append({"step": f"action_{iteration}", "tool": "submit_support_ticket", "input": {"customer_name": customer_name, "issue_description": user_input}})
                obs = TOOL_MAP["submit_support_ticket"](customer_name=customer_name, issue_description=user_input)
                self.trace.append({"step": f"observation_{iteration}", "content": obs})
                
                ticket_id = obs.get("ticket_id", "")
                final_answer = f"Yêu cầu hỗ trợ của {customer_name} đã được ghi nhận thành công. Mã ticket của bạn là: {ticket_id}"
                break
                
            else: 
                # Không cần tool nào (FAQ)
                self.trace.append({"step": "final_answer", "content": "Tổng hợp kết quả trực tiếp."})
                if "bảo hành" in user_text:
                    final_answer = "Chính sách bảo hành pin xe điện VinFast kéo dài 10 năm."
                else:
                    final_answer = "Tôi có thể giải đáp các câu hỏi chung về chính sách và thông tin Vingroup."
                break

        return {
            "answer": final_answer,
            "trace": self.trace,
            "iterations": iteration,
            "status": "completed"
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
