# 白蚁探测结果（毫米波 / 视觉统一用这一条）
std_msgs/Header header

# 本次结果是否有效（窗口完整、推理成功）
bool valid

# 是否检出白蚁（分类模型输出；回归阶段固定 false）
bool detected

# 白蚁置信度 0..1（回归阶段为 0）
float32 confidence

# 回归输出：板厚/活动深度，单位 mm（模型当前输出）
float32 depth_mm

# 本次推理耗时，单位 ms
float32 infer_ms

# 参与本次推理的雷达帧数
uint32 frames

# 数据来源：mmwave / vision / fused
string source

# 原始附加信息（JSON，可为空）
string debug_json
