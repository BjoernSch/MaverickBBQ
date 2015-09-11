<?php
$sqlite3_file = 'maverick.sqlite';
$db = new SQLite3($sqlite3_file);

$stmt = $db->prepare("SELECT DISTINCT id FROM maverick WHERE date >= :date ORDER BY id");
$stmt->bindValue(':date', time() - 300);
$result = $stmt->execute();
$units = array();

while ($row = $result->fetchArray() ) {
$units[] = $row['id'];
}
$result->finalize();
$data=array();
foreach ($units as $unit) {
$stmt2 = $db->prepare("SELECT max(date) as date , id, avg(temperature_1) as temperature_1, avg(temperature_2) as temperature_2 FROM maverick WHERE id = :id AND date >= :date group by strftime('%Y-%m-%dT%H:%M:00.000', date, 'unixepoch') ORDER BY DATE ASC ");
$stmt2->bindValue(':id', $unit);
$stmt2->bindValue(':date', time() - 60 * 60);
$result2 = $stmt2->execute();
$data['data' . $unit]=array();
$data['data' . $unit]['labels']=array();
$data['data' . $unit]['datasets']=array();
$data['data' . $unit]['datasets'][1]=array('label' => 'Temperatur 1', 'data'=>array(),
            'fillColor' => "rgba(220,220,220,0.2)",
            'strokeColor' => "rgba(220,220,220,1)",
            'pointColor' => "rgba(220,220,220,1)",
            'pointStrokeColor' => "#fff",
            'pointHighlightFill' => "#fff",
            'pointHighlightStroke' => "rgba(220,220,220,1)");
$data['data' . $unit]['datasets'][2]=array('label' => 'Temperatur 2', 'data'=>array(),
            'fillColor' => "rgba(151,187,205,0.2)",
            'strokeColor' => "rgba(151,187,205,1)",
            'pointColor' => "rgba(151,187,205,1)",
            'pointStrokeColor' => "#fff",
            'pointHighlightFill' => "#fff",
            'pointHighlightStroke' => "rgba(151,187,205,1)");
while ($row = $result2->fetchArray() ) {
$data['data' . $unit]['labels'][] = date('d.m.Y G:i',$row['date']);
$data['data' . $unit]['datasets'][1]['data'][] = $row['temperature_1'];
$data['data' . $unit]['datasets'][2]['data'][] = $row['temperature_2'];
}
$result2->finalize();
}
echo 'var data = ' . json_encode($data) . ';';
?>
