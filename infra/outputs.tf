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

output "version_desplegada" {
  description = "Commit que se despliega. Compruebalo en la instancia con: curl http://<ip>/api/salud"
  value       = local.repo_version
}

output "comprobar" {
  description = "Cuando el arranque termine (5-10 min) esto responde con la version desplegada"
  value       = "curl http://${aws_eip.plantas.public_ip}/api/salud"
}

output "disco_datos" {
  description = "Disco EBS con el historico. Sobrevive a terraform apply; haz snapshots desde la consola EC2 > Volumes"
  value       = aws_ebs_volume.datos.id
}
