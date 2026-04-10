# 01. System Context Diagram

## Mục đích
Sơ đồ này mô tả bức tranh lớn của hệ thống: các hệ nghiệp vụ hiện có, Agri OS Core, người dùng chính, các kênh vào/ra, và lớp AI/harness trong tương lai.

## Mermaid
```mermaid
flowchart TB
    subgraph Users["Actors / Users"]
        Farmer["Farmer / Farm Operator"]
        Ops["Ops / QC / Sales / Admin"]
        Customer["Customer"]
        Manager["Management / Founder"]
    end

    subgraph Channels["Channels / Touchpoints"]
        Zalo["Zalo / Messenger / Chat"]
        Web["Web / App / Admin UI"]
        QR["QR Traceability Page"]
        Import["Manual Import / CSV / API"]
    end

    subgraph External["Systems of Record"]
        LiteFarm["LiteFarm\nFarm Ops / Plot / Crop Cycle / Field Tasks"]
        ERP["ERPNext\nOrder / Inventory / Stock / Invoice"]
        CRM["CRM\nCustomer / Segment / Lifecycle / Interaction"]
    end

    subgraph Core["Agri OS Core"]
        CoreAPI["Core API / Command Gateway"]
        CorePolicy["Policy + Workflow Engine"]
        CoreState["Canonical Core\nIdentity / Event Log / Read Models / Permissions"]
    end

    subgraph FutureAI["Future AI / Agent Layer"]
        BrainAdapter["Brain Adapter / Harness Layer"]
        RoleAgents["Role-based Agents\n(Customer Care / Order Ops / QC / Farmer Assistant)"]
    end

    Farmer --> Web
    Ops --> Web
    Customer --> Zalo
    Customer --> QR
    Manager --> Web

    Zalo --> CoreAPI
    Web --> CoreAPI
    Import --> CoreAPI
    QR --> CoreState

    LiteFarm <--> CoreAPI
    ERP <--> CoreAPI
    CRM <--> CoreAPI

    CoreAPI --> CorePolicy
    CorePolicy --> CoreState
    CoreState --> Web
    CoreState --> QR

    BrainAdapter <--> CoreAPI
    BrainAdapter --> RoleAgents
```
