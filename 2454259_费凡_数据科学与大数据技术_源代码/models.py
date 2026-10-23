class Patient:
    def __init__(self, pid: str, name: str, chief_complaint: str, init_weight: int, target_resource: str = "R1-抢救室", treatment_required: int = 3):
        self.id = pid                     # 患者编号
        self.name = name                  # 姓名
        self.chief_complaint = chief_complaint # 临床主诉文本
        self.weight = init_weight         # 动态总权重 (随等待步长动态自增)
        self.init_weight = init_weight    # 初始评估危险分
        self.wait_time = 0                # 已等待的时间步长
        self.target_resource = target_resource # 自动标定的流向科室类型
        self.treatment_left = treatment_required # 剩余就诊在治周期
        self.level = "III级(急症)"         # 临床危急分级状态字

    def __repr__(self):
        return f"[{self.id}]{self.name}(权重:{self.weight}, 剩:{self.treatment_left}步)"


class ResourceSlot:
    def __init__(self, r_code: str, r_type: str, r_id: int):
        self.code = r_code             # 资源编码 (如 R1, R2)
        self.type = r_type             # 资源类目汉字描述 (如 抢救室)
        self.id = r_id                 # 槽位物理编号 (如 1号机、2号机)
        self.current_patient = None    # 当前占用者引用 (None代表闲置)
        self.preempted_stack = []      # 后进先出(LIFO)被抢占上下文顺序挂起栈
        self.status = "Green"          # 状态字: Green-空闲, Yellow-普通治疗, Red-强行抢占