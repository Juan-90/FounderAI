# Objetivo  
Desenvolver um MVP de **Web App / SaaS** para **saúde de idosos** que permita:
- Registro e controle diário de medicamentos com alarmes configuráveis.
- Botão de pânico que notifica cuidadores em tempo real.
- Interface de alta acessibilidade (fonte grande, contraste alto, navegação por teclado).

# Usuários  
| Papel | Perfil | Necessidades |
|-------|--------|--------------|
| Idoso | Usuário final, com baixa visão ou mobilidade reduzida | Fonte grande, contraste alto, navegação simples, lembretes de medicação. |
| Cuidador | Responsável pelo idoso (família ou profissional) | Receber notificações de pânico, visualizar histórico de medicação, configurar alarmes. |
| Administrador | Operador do SaaS | Gerenciar contas de usuários, monitorar uso, configurar políticas de segurança. |

# MVP  
## Recursos CRUD / APIs  
| Entidade | Operação | Endpoint (exemplo) | Descrição |
|----------|----------|--------------------|-----------|
| **Usuário** | Create | POST `/api/users` | Cadastro de idoso ou cuidador. |
| | Read | GET `/api/users/:id` | Obter dados do usuário. |
| | Update | PUT `/api/users/:id` | Atualizar perfil (nome, contato, preferências). |
| | Delete | DELETE `/api/users/:id` | Desativar conta (soft delete). |
| **Medicamento** | Create | POST `/api/medicamentos` | Registrar novo medicamento. |
| | Read | GET `/api/medicamentos/:id` | Obter detalhes. |
| | Update | PUT `/api/medicamentos/:id` | Alterar dose ou horário. |
| | Delete | DELETE `/api/medicamentos/:id` | Remover registro. |
| **Alarme** | Create | POST `/api/alarme` | Configurar lembrete. |
| | Read | GET `/api/alarme/:id` | Verificar status. |
| | Update | PUT `/api/alarme/:id` | Ajustar horário ou repetir. |
| | Delete | DELETE `/api/alarme/:id` | Cancelar alarme. |
| **Pânico** | Create | POST `/api/panico` | Enviar alerta de pânico. |
| | Read | GET `/api/panico/:id` | Histórico de pânico. |

## Persistência  
- Banco de dados relacional (PostgreSQL) com tabelas: `users`, `medicamentos`, `alarme`, `panico`.  
- Tabelas de auditoria (`audit_log`) para registrar alterações críticas.  
- Backup diário automático e retenção de 30 dias.

## Listagem  
- **Dashboard**: lista de medicamentos com status (tomado / pendente) e próximos alarmes.  
- **Histórico de pânico**: tabela paginada com data, hora e destinatário.  
- **Configurações**: lista de usuários vinculados a cada conta (para cuidadores).

## Exclusão/Cancelamento  
- Operações de delete são *soft delete* (campo `deleted_at`).  
- Usuário pode cancelar alarmes individuais; pânico não pode ser excluído, apenas marcado como “resolvido”.  
- Administrador pode reativar contas excluídas.

# Restrições  
- **Tempo de entrega**: 6 semanas (incluindo testes).  
- **Tecnologias**: React (frontend), Node.js/Express (backend), PostgreSQL (DB), Docker (containerização).  
- **Acessibilidade**: WCAG 2.1 AA, fonte mínima 18px, contraste 4.5:1.  
- **Segurança**: JWT para autenticação, HTTPS obrigatório, OWASP Top 10 mitigado.  
- **Escalabilidade**: Design monolítico inicial, mas com APIs REST para futura expansão.  
- **Orçamento**: Máximo de 3.000 USD em infraestrutura (AWS Lightsail ou equivalente).  

# Não-objetivos  
- Integração com dispositivos IoT (sensores de pressão, batimentos).  
- Análise preditiva de saúde ou machine learning.  
- Tradução multilíngue (apenas português e inglês).  
- Funcionalidades de pagamento ou faturamento interno.  
- Suporte a múltiplos idiomas ou personalização de temas.