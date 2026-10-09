# Objetivo  
Desenvolver um módulo web para a vitrine **Shop‑Car** que permita aos usuários visualizar, filtrar e solicitar propostas de carros usados e seminovos, além de simular financiamento.

# Usuários  
- **Compradores**: pessoas que buscam carros, filtram por ano, marca e preço, simulam financiamento e enviam propostas.  
- **Vendedores**: proprietários ou concessionárias que cadastrarem veículos e acompanhem propostas recebidas.  
- **Administradores**: gerenciam usuários, veículos e visualizam métricas básicas.

# MVP  

## Recursos CRUD / APIs  
| Entidade | Operações | Endpoints (exemplo) | Observações |
|----------|-----------|---------------------|-------------|
| **Carro** | Create, Read (list & detail), Update, Delete | `POST /api/cars`, `GET /api/cars`, `GET /api/cars/:id`, `PUT /api/cars/:id`, `DELETE /api/cars/:id` | Apenas vendedores autenticados podem criar/editar/excluir. |
| **Proposta** | Create, Read (list & detail), Update (status), Delete | `POST /api/proposals`, `GET /api/proposals`, `GET /api/proposals/:id`, `PUT /api/proposals/:id`, `DELETE /api/proposals/:id` | Vendedores recebem notificações de novas propostas. |
| **Simulação** | Read (calculadora) | `POST /api/simulations` | Recebe `car_id`, `valor_financiado`, `prazo`, `taxa_juros` e devolve parcelas. |

## Persistência  
- Banco de dados relacional (PostgreSQL) com tabelas: `users`, `cars`, `proposals`, `simulations`.  
- Relacionamentos: `user (1) – cars (N)`, `car (1) – proposals (N)`.  
- Índices nos campos de filtro: `year`, `brand`, `price`.  

## Listagem  
- **Carros**: página `/cars` com filtros avançados (ano, marca, faixa de preço) e paginação (20 por página).  
- **Propostas**: `/proposals` para vendedores, com filtros por status (pendente, aceita, rejeitada).  

## Exclusão/Cancelamento  
- Vendedores podem excluir carros que ainda não tenham propostas pendentes.  
- Compradores podem cancelar propostas pendentes antes de aceitação.  
- Operações de exclusão são soft‑delete (campo `deleted_at`) para auditoria.

# Restrições  
- **Tempo**: MVP deve estar funcional em 4 semanas de desenvolvimento.  
- **Tecnologia**: Frontend em React (Next.js) + Tailwind CSS; Backend em Node.js (Express) + TypeScript.  
- **Escalabilidade**: Design modular, API RESTful, uso de cache Redis para listagens frequentes.  
- **Segurança**: JWT para autenticação, validação de entrada, proteção contra CSRF/XSS.  
- **Deploy**: Dockerizado, pronto para execução em Kubernetes ou Heroku.  

# Não‑objetivos  
- Integração com sistemas de pagamento ou financiamento bancário.  
- Análise de dados avançada ou dashboards de BI.  
- Suporte multilíngue ou internacionalização.  
- Funcionalidades de chat ao vivo ou suporte 24/7.  
- Marketplace de revenda de carros (venda direta entre usuários).