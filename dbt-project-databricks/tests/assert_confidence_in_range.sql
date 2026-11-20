select detection_id, confidence_score
from {{ ref('fct_bird_detections') }}
where confidence_score < 0 or confidence_score > 1