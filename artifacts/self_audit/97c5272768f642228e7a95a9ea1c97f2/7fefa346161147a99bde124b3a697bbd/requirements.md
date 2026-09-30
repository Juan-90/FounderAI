# Objetivo  
Desenvolver um sistema de agendamento online para barbearia, permitindo que clientes marquem, visualizem e cancelem serviços, e que o proprietário gerencie a agenda e os profissionais.

# Usuários  
- **Cliente**: busca horários disponíveis, agenda serviços e cancela agendamentos.  
- **Barbeiro/Proprietário**: visualiza agenda completa, confirma ou rejeita agendamentos e exclui compromissos.

# MVP  
- **Recursos CRUD / APIs**  
  - `POST /agendamentos`: criar agendamento (cliente, serviço, horário).  
  - `GET /agendamentos`: listar agendamentos do usuário (cliente ou barbeiro).  
  - `GET /agendamentos/{id}`: detalhar agendamento.  
  - `PUT /agendamentos/{id}`: atualizar horário ou serviço (cliente).  
  - `DELETE /agendamentos/{id}`: cancelar agendamento (cliente ou barbeiro).  
- **Persistência**  
  - Banco relacional (PostgreSQL) com tabelas: `clientes`, `barbeiros`, `serviços`, `agendamentos`.  
  - Índices nos campos `data_hora`, `barbeiro_id`, `cliente_id`.  
- **Listagem**  
  - Paginação simples (10 por página).  
  - Filtros por data, barbeiro e status (agendado, cancelado, concluído).  
- **Exclusão/Cancelamento**  
  - Soft delete: campo `cancelado_em`.  
  - Notificação por e‑mail (opcional) ao cancelar.

# Restrições  
- Front‑end mínimo: SPA em React ou Vue, consumindo API REST.  
- Backend em Node.js (Express) ou Python (FastAPI).  
- Deploy em plataforma SaaS (Heroku, Render, Vercel).  
- Autenticação JWT, sem integração de terceiros.  
- Tempo de resposta ≤ 200 ms para chamadas CRUD.  
- Escalabilidade horizontal mínima (podemos usar Docker).  

# Não‑objetivos  
- Integração com sistemas de pagamento.  
- Sistema de avaliação de barbeiros.  
- Chat ao vivo entre cliente e barbeiro.  
- Relatórios avançados (dashboards).