import tkinter as tk
from tkinter import messagebox, ttk
from models import Patient
from structures import MedicalTrie, IndexedMaxHeap
from manager import ResourceManager, SimulationEngine

class EmergencyDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("急诊医疗资源动态抢占调度可视化看板")
        self.root.geometry("1250x820")
        self.root.configure(bg="#F5F5F5")

        self.trie = MedicalTrie()
        self.max_heap = IndexedMaxHeap()
        self.rm = ResourceManager()
        self.engine = SimulationEngine(self.rm, self.max_heap)

        self.pid_counter = 20
        self.flash_state = True
        self.flash_widgets = [] # 收集当前处于抢占激发期的物理卡片容器句柄

        self._setup_ui()
        self._run_flash_loop()

    def _setup_ui(self):
        # 1. [面板 1] 顶部语义病历输入与前置过滤面板
        emr_frame = tk.LabelFrame(self.root, text=" [面板 1] 电子病历（EMR）语义解析与分诊判定面板 ", font=("微软雅黑", 11, "bold"), bg="white", fg="#333333", bd=2, relief="groove")
        emr_frame.pack(fill="x", padx=15, pady=10)

        input_layout = tk.Frame(emr_frame, bg="white")
        input_layout.pack(fill="x", padx=10, pady=5)

        tk.Label(input_layout, text="任意手写录入患者主诉:", font=("微软雅黑", 10, "bold"), bg="white").pack(side="left", padx=5)
        self.entry_text = tk.Entry(input_layout, font=("微软雅黑", 10), width=45, bd=2, relief="sunken")
        self.entry_text.insert(0, "马路上突然倒地，心搏骤停！120正在做心肺复苏！")
        self.entry_text.pack(side="left", padx=5)

        tk.Label(input_layout, text="患者姓名:", font=("微软雅黑", 10), bg="white").pack(side="left", padx=5)
        self.entry_name = tk.Entry(input_layout, font=("微软雅黑", 10), width=8, bd=2, relief="sunken")
        self.entry_name.insert(0, "秦建华")
        self.entry_name.pack(side="left", padx=5)

        tk.Button(input_layout, text="提交分诊录入", font=("微软雅黑", 10, "bold"), bg="#107C41", fg="white", bd=0, padx=12, command=self.handle_parse_patient).pack(side="left", padx=5)
        tk.Button(input_layout, text="注入全满压力剧本", font=("微软雅黑", 10, "bold"), bg="#8764B8", fg="white", bd=0, padx=12, command=self.load_demo_script).pack(side="left", padx=5)

        result_layout = tk.Frame(emr_frame, bg="#FAFAFA", bd=1, relief="solid")
        result_layout.pack(fill="x", padx=10, pady=8)
        
        tk.Label(result_layout, text="Trie树检索高亮展示: ", font=("微软雅黑", 10, "bold"), bg="#FAFAFA").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.lbl_highlight = tk.Text(result_layout, font=("微软雅黑", 11), height=2, bg="#FAFAFA", bd=0, wrap="word")
        self.lbl_highlight.grid(row=0, column=1, sticky="we", padx=5, pady=3)
        self.lbl_highlight.config(state="disabled")

        self.lbl_score = tk.Label(result_layout, text="初始评估危险权重分: -- 分 | 危急分级: -- | 标定导医去向: --", font=("微软雅黑", 11, "bold"), fg="#D83B01", bg="#FAFAFA")
        self.lbl_score.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=3)

        middle_frame = tk.Frame(self.root, bg="#F5F5F5")
        middle_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # 2. [面板 2] 排队看板视口展示区
        queue_frame = tk.LabelFrame(middle_frame, text=" [面板 2] 急诊排队大顶堆动态看板", font=("微软雅黑", 11, "bold"), bg="white", fg="#333333", bd=2, relief="groove")
        queue_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.tree_queue = ttk.Treeview(queue_frame, columns=("id", "name", "level", "weight", "init_weight", "res", "wait"), show="headings")
        headings = [("id", "患者编号", 70), ("name", "患者姓名", 70), ("level", "病情定级", 95), ("weight", "动态总权重", 80), ("init_weight", "初始分", 55), ("res", "标定资源", 90), ("wait", "已等时步", 55)]
        for col, text, width in headings:
            self.tree_queue.heading(col, text=text)
            self.tree_queue.column(col, width=width, anchor="center")
        self.tree_queue.pack(fill="both", expand=True, padx=10, pady=10)

        # 3. [面板 3] 公共物理资源床位色块展示网格
        self.res_frame = tk.LabelFrame(middle_frame, text=" [面板 3] 医疗核心资源网格监控屏", font=("微软雅黑", 11, "bold"), bg="white", fg="#333333", bd=2, relief="groove")
        self.res_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        canvas = tk.Canvas(self.res_frame, bg="white", bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.res_frame, orient="vertical", command=canvas.yview)
        self.grid_container = tk.Frame(canvas, bg="white")
        
        self.grid_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.canvas_window = canvas.create_window((0, 0), window=self.grid_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.canvas_window, width=e.width))
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        # 4. 底部时钟计数长条与扩展日志区
        bottom_frame = tk.Frame(self.root, bg="#F5F5F5")
        bottom_frame.pack(fill="x", padx=15, pady=10)

        tk.Button(bottom_frame, text="推进单步时间步长", font=("微软雅黑", 11, "bold"), bg="#0078D4", fg="white", bd=0, padx=20, pady=5, command=self.handle_next_step).pack(side="left", padx=5)
        self.lbl_step = tk.Label(bottom_frame, text="当前步长时钟: Step 0", font=("微软雅黑", 11, "bold"), fg="#0078D4", bg="#F5F5F5")
        self.lbl_step.pack(side="right", padx=10)

        log_frame = tk.LabelFrame(self.root, text="仿真运行日志动态监控区", font=("微软雅黑", 10, "bold"), bg="white")
        log_frame.pack(fill="x", padx=15, pady=(0, 10))
        self.txt_log = tk.Text(log_frame, font=("Consolas", 10), height=10, bg="#252526", fg="#D4D4D4", state="disabled")
        self.txt_log.pack(fill="x", padx=5, pady=5)

        self.refresh_all_views()

    def load_demo_script(self):
        #注入饱和负荷边界场景初始预设
        self.max_heap = IndexedMaxHeap()
        self.rm = ResourceManager()
        self.engine = SimulationEngine(self.rm, self.max_heap)
        self.engine.current_step = 0
        self.lbl_step.config(text="当前步长时钟: Step 0")
        
        presets = [
            ("R1", 1, "P003", "孙建设", "喝完酒后突然大出血", 92), ("R1", 2, "P010", "陈洁", "咳嗽时突然咯血", 75),
            ("R1", 3, "P014", "沈明", "吃海鲜后全身起红斑过敏性休克", 45), ("R2", 1, "P004", "李秀英", "晚上睡觉突然呼吸困难，不能平卧", 50),
            ("R2", 2, "P011", "褚玉兰", "老人清晨昏迷，有糖尿病史", 80), ("R3", 1, "P007", "郑国强", "夜间突发胸痛，胸口像压了大石头", 70),
            ("R3", 2, "P012", "卫东", "突发剧烈胸痛", 70), ("R4", 1, "P001", "赵强", "突发剧烈胸痛2小时伴恶心呕吐肚子硬", 75),
            ("R5", 1, "P015", "韩梅", "感觉头晕，稍微有些恶心，想开点降压药", 20) 
        ]
        for r_code, r_id, pid, p_name, text, score in presets:
            p = Patient(pid, p_name, text, score, target_resource=f"{r_code}-资源", treatment_required=3)
            p.level = self.trie.get_injury_level(score)
            for slot in self.rm.slots:
                if slot.code == r_code and slot.id == r_id:
                    slot.current_patient = p
                    slot.status = "Yellow"
        self.append_log("当前全院 5类 9项 核心医疗资源已被全额满载占用。")
        self.refresh_all_views()

    def handle_parse_patient(self):
        text = self.entry_text.get().strip()
        name = self.entry_name.get().strip()
        if not text or not name:
            messagebox.showwarning("警告", "主诉文本和患者姓名均不能为空！")
            return

        matches, score, target_res = self.trie.parse_text(text)
        injury_lvl = self.trie.get_injury_level(score)
        
        self.lbl_highlight.config(state="normal")
        self.lbl_highlight.delete("1.0", tk.END)
        self.lbl_highlight.insert(tk.END, text)
        for word, _ in matches:
            start_pos = "1.0"
            while True:
                pos = self.lbl_highlight.search(word, start_pos, stopindex=tk.END)
                if not pos: break
                end_pos = f"{pos}+{len(word)}c"
                self.lbl_highlight.tag_add("highlight", pos, end_pos)
                start_pos = end_pos
        self.lbl_highlight.tag_config("highlight", foreground="#D83B01", font=("微软雅黑", 11, "bold"))
        self.lbl_highlight.config(state="disabled")

        self.lbl_score.config(text=f"初始评估危险权重分: {score} 分 | 危急分级: {injury_lvl} | 导医分流去向: [{target_res}]")
        pid = f"P{self.pid_counter:03d}"
        self.pid_counter += 1 
        
        new_patient = Patient(pid, name, text, init_weight=score, target_resource=target_res, treatment_required=2)
        new_patient.level = injury_lvl
        self.max_heap.push(new_patient)
        self.append_log(f"病情输入与标定 -> 患者 [{pid}]{name} 评定为 {injury_lvl}，已推进大顶堆优先排队。")
        self.refresh_all_views()

    def handle_next_step(self):
        self.engine.next_step()
        self.lbl_step.config(text=f"current_step: Step {self.engine.current_step}")
        for log in self.engine.logs: self.append_log(log)
        self.refresh_all_views()

    def refresh_all_views(self):
        self._render_max_heap_tree()
        self._render_resource_grids()

    def _render_max_heap_tree(self):
        for item in self.tree_queue.get_children(): self.tree_queue.delete(item)
        for p in self.max_heap.get_all_patients_sorted_copy():
            p.level = self.trie.get_injury_level(p.weight)
            self.tree_queue.insert("", tk.END, values=(p.id, p.name, p.level, p.weight, p.init_weight, p.target_resource, p.wait_time))

    def _render_resource_grids(self):
        for widget in self.grid_container.winfo_children(): widget.destroy()
        self.flash_widgets = [] 
        
        colors = {"Green": ("#E1F5FE", "#0288D1", "空闲开放"), "Yellow": ("#FFF9C4", "#FBC02D", "普通患者治疗中"), "Red": ("#FFCDD2", "#D32F2F", "特危强行抢占占用!!")}
        for idx, slot in enumerate(self.rm.slots):
            bg_color, fg_color, status_text = colors[slot.status]
            card = tk.Frame(self.grid_container, bg=bg_color, bd=1, relief="solid", padx=12, pady=8, height=125)
            card.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="nsew")
            card.pack_propagate(False) # 裁切溢出文字Bug
            
            tk.Label(card, text=f"{slot.code} - {slot.type} - {slot.id}号", font=("微软雅黑", 10, "bold"), bg=bg_color, fg=fg_color).pack(anchor="w")
            tk.Label(card, text=status_text, font=("微软雅黑", 9, "italic"), bg=bg_color).pack(anchor="w")
            p_name = f"[{slot.current_patient.id}]{slot.current_patient.name}" if slot.current_patient else "无"
            p_left = f"(剩 {slot.current_patient.treatment_left} 步)" if slot.current_patient else ""
            tk.Label(card, text=f"占用者: {p_name} {p_left}", font=("微软雅黑", 9), bg=bg_color).pack(anchor="w")
            
            if slot.preempted_stack:
                pre_txt = ", ".join([f"[{p.id}]{p.name}" for p in slot.preempted_stack])
                tk.Label(card, text=f"挂起回流等待: {pre_txt}", font=("微软雅黑", 9, "bold"), fg="#D32F2F", bg=bg_color).pack(anchor="w")
            if slot.status == "Red": self.flash_widgets.append((card, bg_color))

        self.grid_container.grid_columnconfigure(0, weight=1, uniform="equal_cols")
        self.grid_container.grid_columnconfigure(1, weight=1, uniform="equal_cols")

    def _run_flash_loop(self):
        #依赖Tkinter异步 after 维护的闪烁闭环
        self.flash_state = not self.flash_state
        for widget, original_bg in self.flash_widgets:
            color = "#FF1744" if self.flash_state else original_bg
            widget.config(bg=color)
            for child in widget.winfo_children(): child.config(bg=color, fg="white" if self.flash_state else "#D32F2F")
        self.root.after(500, self._run_flash_loop)

    def append_log(self, msg):
        self.txt_log.config(state="normal")
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = EmergencyDashboard(root)
    root.mainloop()