from models import ResourceSlot, Patient
from structures import IndexedMaxHeap

class ResourceManager:
    def __init__(self):
        self.slots = []
        self._init_resources()

    def _init_resources(self):
        #构建 5 类 9 项医疗物理槽位资源池
        for i in range(1, 4): self.slots.append(ResourceSlot("R1", "抢救室", i))
        for i in range(1, 3): self.slots.append(ResourceSlot("R2", "ICU床位", i))
        for i in range(1, 3): self.slots.append(ResourceSlot("R3", "CT机", i))
        for i in range(1, 2): self.slots.append(ResourceSlot("R4", "手术室", i))
        for i in range(1, 2): self.slots.append(ResourceSlot("R5", "ECMO", i))

    def get_slots_by_target(self, target_resource: str):
        return [s for s in self.slots if s.code == target_resource.split("-")[0]]

    def allocate_or_preempt(self, patient: Patient, target_resource: str) -> str:
        type_slots = self.get_slots_by_target(target_resource)
        if not type_slots: return f"系统无此资源类型: {target_resource}"
        
        # 1. 搜寻是否存在闲置绿灯槽位，有则直接进驻
        for slot in type_slots:
            if slot.current_patient is None:
                slot.current_patient = patient
                slot.status = "Yellow"
                return f"[分配成功] 患者 {patient.name} 进入 {slot.code}-{slot.type}-{slot.id}号 治疗。"

        # 2. 资源全满，利用 lambda 定向锁定房内在治患者里动态分值垫底的单项卡片
        target_slot = min(type_slots, key=lambda s: s.current_patient.weight)
        
        # 3. 满足优先级抢占条件，切断旧指针，将其历史上下文封存压入 LIFO 顺序栈中
        if patient.weight > target_slot.current_patient.weight:
            preempted_patient = target_slot.current_patient
            target_slot.preempted_stack.append(preempted_patient) 
            target_slot.current_patient = patient
            target_slot.status = "Red" # 触发高频红色物理闪烁
            # 此处显式调用 preempted_patient.weight 规避对象覆盖引发的分值同步Bug
            return f"[强行抢占] {patient.level} 患者 {patient.name}(分:{patient.weight}) 强行中断并抢占了 {target_slot.code}-{target_slot.type}号 的原占用者 {preempted_patient.name}(分:{preempted_patient.weight})。"
        
        return f"[资源受限] 目标资源已满，当前最低占用者为 {target_slot.current_patient.name}({target_slot.current_patient.weight}分)。"


class SimulationEngine:
    def __init__(self, resource_manager: ResourceManager, queue_heap: IndexedMaxHeap):
        self.rm = resource_manager
        self.queue = queue_heap
        self.current_step = 0
        self.logs = []

    def next_step(self):
        self.current_step += 1
        self.logs = [] 
        
        # 1. 遍历排队列表，对所有滞留个体触发恶化公式加成 (定时自增8分)
        p_ids = list(self.queue.pos_map.keys())
        for pid in p_ids:
            idx = self.queue.pos_map[pid]
            p = self.queue.heap[idx]
            old_w = p.weight
            p.wait_time += 1
            new_weight = p.init_weight + (p.wait_time * 8) 
            self.queue.update_weight(p.id, new_weight)
            self.logs.append(f"时步恶化 -> 患者 {p.name} 延迟等待中，分值变动: {old_w}分 -> {new_weight}分。")

        # 2. 在治重症生命周期扣减，耗尽则出院，并自动 pop() 弹出恢复挂起栈顶个体
        for slot in self.rm.slots:
            if slot.current_patient:
                slot.current_patient.treatment_left -= 1
                if slot.current_patient.treatment_left <= 0:
                    finished_p = slot.current_patient
                    self.logs.append(f"完成出院 -> 患者 {finished_p.name} 治疗结束，顺利离开 {slot.code}-{slot.type}。")
                    
                    if slot.preempted_stack:
                        restored_p = slot.preempted_stack.pop() 
                        slot.current_patient = restored_p
                        slot.status = "Red" if slot.preempted_stack else "Yellow"
                        self.logs.append(f"[恢复治疗] 资源释放，自动从后进先出栈弹出被挂起患者 {restored_p.name} 回流治疗。")
                    else:
                        slot.current_patient = None
                        slot.status = "Green"

        # 3. 彻底修复队头阻塞问题的多通道无阻塞独立流转并行流调度算法
        deferred_patients = []  # 暂存本步长内因科室爆满被迫继续留在看板内的要素
        
        while not self.queue.is_empty():
            top_patient = self.queue.pop_max()  # 依次审阅当前全院最高危个体
            target_res = top_patient.target_resource
            res_msg = self.rm.allocate_or_preempt(top_patient, target_res)
            
            if "[分配成功]" in res_msg or "[强行抢占]" in res_msg:
                self.logs.append(res_msg)
            else:
                # 跨越当前卡死通道瓶颈，允许指针穿透审查队列后方其余个体的对口资源空闲情况
                self.logs.append(f"分流受阻 -> 患者 {top_patient.name}({top_patient.weight}分) 申请 {target_res}，{res_msg} 门槛不足。")
                deferred_patients.append(top_patient)  # 请入暂存区，不阻塞他人

        # 4. 轮询结束，将暂存列表要素统一重推(push)回优先队列大顶堆
        for p in deferred_patients:
            self.queue.push(p)