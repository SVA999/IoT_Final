output "ip_publica" {
  description = "IP elastica fija"
  value       = aws_eip.plantas.public_ip
}

output "front" {
  value = "http://${aws_eip.plantas.public_ip}"
}

output "orion" {
  value = "http://${aws_eip.plantas.public_ip}:1036/version"
}

output "agente_iot_para_el_device" {
  description = "URL que debe usar el end device"
  value       = "http://${aws_eip.plantas.public_ip}:7896/iot/json?k=plantas2026&i=planta01"
}

output "ssh" {
  value = "ssh -i labsuite.pem ubuntu@${aws_eip.plantas.public_ip}"
}
