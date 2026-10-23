class TrieNode:
    def __init__(self):
        self.children = {}  # 指向子节点的哈希字典域 (键为字符，值为TrieNode)
        self.weight = 0     # 词尾危险加权分，非词尾为0
        self.word = None    # 词尾明文词条文本


class MedicalTrie:
    def __init__(self):
        self.root = TrieNode()
        self._load_default_vocabulary()

    def _load_default_vocabulary(self):
        self.vocab_config = {
            "窒息": (92, "R1-抢救室"), "昏迷": (85, "R1-抢救室"), "抽搐": (65, "R1-抢救室"), 
            "中毒": (70, "R1-抢救室"), "发热": (15, "R1-抢救室"), "咯血": (75, "R1-抢救室"), 
            "大出血": (92, "R1-抢救室"), "严重车祸": (90, "R1-抢救室"),
            "呼吸困难": (80, "R2-ICU床位"), "脑梗死": (88, "R2-ICU床位"),
            "脑出血": (95, "R3-CT机"), "脑外伤": (85, "R3-CT机"), "突发胸痛": (70, "R3-CT机"), 
            "胸痛": (55, "R3-CT机"), "急性腹痛": (40, "R3-CT机"),
            "主动脉夹层": (96, "R4-手术室"), "肚子硬": (75, "R4-手术室"), "骨折": (45, "R4-手术室"),
            "心搏骤停": (99, "R5-ECMO"), "心跳骤停": (99, "R5-ECMO")
        }
        for word, (weight, _) in self.vocab_config.items():
            self.insert(word, weight)

    def insert(self, word: str, weight: int):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.weight = weight
        node.word = word

    def parse_text(self, text: str):
        #双层滑动窗口扫描匹配算法，支持嵌套、前缀重叠词的完整风险提取
        matched_details = []
        total_score = 0
        determined_resource = "R1-抢救室" 
        max_word_weight = -1
        
        n = len(text)
        for i in range(n):
            node = self.root
            for j in range(i, n):
                if text[j] not in node.children:
                    break
                node = node.children[text[j]]
                if node.weight > 0: # 命中关键词
                    matched_details.append((node.word, node.weight))
                    total_score += node.weight
                    # 动态锁定分值最高的独立核心词标定去向
                    if node.weight > max_word_weight:
                        max_word_weight = node.weight
                        determined_resource = self.vocab_config[node.word][1]
                        
        if "心搏骤停" in text or "心跳骤停" in text:
            determined_resource = "R5-ECMO" # 特危处理

        return list(set(matched_details)), total_score, determined_resource

    def get_injury_level(self, score: int) -> str:
        if score >= 95: return "I级(特级濒危)"
        elif score >= 75: return "II级(危重)"
        elif score >= 45: return "III级(急症)"
        else: return "IV级(非急症)"


class IndexedMaxHeap:
    #带反向散列表映射的大顶堆
    def __init__(self):
        self.heap = []       # 顺序存储 Patient 对象的动态一维表
        self.pos_map = {}    # 反向位置散列表: id -> heap_index

    def __len__(self): return len(self.heap)

    def is_empty(self): return len(self.heap) == 0

    def _swap(self, i: int, j: int):
        #对调堆中元素，同步维护 pos_map 下标索引
        self.heap[i], self.heap[j] = self.heap[j], self.heap[i]
        self.pos_map[self.heap[i].id] = i
        self.pos_map[self.heap[j].id] = j

    def _sift_up(self, idx: int):
        while idx > 0:
            parent = (idx - 1) // 2
            if self.heap[idx].weight > self.heap[parent].weight:
                self._swap(idx, parent)
                idx = parent
            else: break

    def _sift_down(self, idx: int):
        n = len(self.heap)
        while 2 * idx + 1 < n:
            left = 2 * idx + 1
            right = left + 1
            largest = left
            if right < n and self.heap[right].weight > self.heap[left].weight:
                largest = right
            if self.heap[largest].weight > self.heap[idx].weight:
                self._swap(idx, largest)
                idx = largest
            else: break

    def push(self, patient):
        if patient.id in self.pos_map: return 
        self.heap.append(patient)
        idx = len(self.heap) - 1
        self.pos_map[patient.id] = idx
        self._sift_up(idx)

    def pop_max(self):
        if not self.heap: return None
        self._swap(0, len(self.heap) - 1)
        max_patient = self.heap.pop()
        del self.pos_map[max_patient.id]
        if self.heap: self._sift_down(0)
        return max_patient

    def update_weight(self, patient_id: str, new_weight: int):
        #利用哈希常数定位，智能引导执行对数级上浮或下沉调序
        if patient_id not in self.pos_map: return
        idx = self.pos_map[patient_id]
        old_weight = self.heap[idx].weight
        self.heap[idx].weight = new_weight
        if new_weight > old_weight: self._sift_up(idx)
        elif new_weight < old_weight: self._sift_down(idx)

    def get_all_patients_sorted_copy(self):
        #克隆大顶堆并执行完整排干弹栈，提供有副本用于前端 Treeview 表格投影
        temp_heap = IndexedMaxHeap()
        for p in self.heap: temp_heap.push(p)
        sorted_list = []
        while not temp_heap.is_empty(): sorted_list.append(temp_heap.pop_max())
        return sorted_list