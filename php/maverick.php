<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>BBQ-Thermometer</title>
<meta http-equiv="refresh" content="300">
 <script src="jquery.min.js"></script>
 <script src="Chart.js"></script>
 <script src="data.php"></script>
</head>
<body>
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

foreach ($units as $unit) {
echo '<h1>' . $unit . '</h1>';
$stmt = $db->prepare("SELECT date, id, temperature_1, temperature_2 FROM maverick WHERE id = :id ORDER BY DATE DESC LIMIT 1");
$stmt->bindValue(':id', $unit);
$result = $stmt->execute();
while ($row = $result->fetchArray() ) {
echo 'Sensor 1: ' . $row['temperature_1'] .' °C<br>';
echo 'Sensor 2: ' . $row['temperature_2'] .' °C<br>';
echo '<canvas id="Chart' . $unit. '" width="400" height="400"></canvas>';
echo '<script>';
echo 'var ctx' . $unit. ' = $("#Chart' . $unit. '").get(0).getContext("2d");';
echo 'var chart' . $unit. ' = new Chart(ctx' . $unit. ').Line(data.data' . $unit. ');';
echo '</script>';
echo '<br>';
echo date(DATE_RFC2822,$row['date']);
}
}
?>
</body>
</html>
