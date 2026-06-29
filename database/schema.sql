/*
  Om Events domain reference for Microsoft SQL Server 2019+.
  Django migrations in events/migrations are the executable source of truth and
  must be used for application tables. This script documents the wider normalized
  roadmap, reporting views and stored procedures for database teams.
*/
SET XACT_ABORT ON;
SET NOCOUNT ON;
GO

CREATE TABLE dbo.Roles (
    Id int IDENTITY PRIMARY KEY,
    Name nvarchar(50) NOT NULL UNIQUE
);
CREATE TABLE dbo.Users (
    Id int IDENTITY PRIMARY KEY,
    Name nvarchar(120) NOT NULL,
    Email nvarchar(255) NOT NULL UNIQUE,
    PasswordHash nvarchar(255) NOT NULL,
    RoleId int NOT NULL REFERENCES dbo.Roles(Id),
    IsActive bit NOT NULL CONSTRAINT DF_Users_Active DEFAULT 1,
    CreatedAt datetimeoffset NOT NULL CONSTRAINT DF_Users_Created DEFAULT SYSDATETIMEOFFSET(),
    UpdatedAt datetimeoffset NOT NULL CONSTRAINT DF_Users_Updated DEFAULT SYSDATETIMEOFFSET()
);
CREATE INDEX IX_Users_Email ON dbo.Users(Email);

CREATE TABLE dbo.Permissions (Id int IDENTITY PRIMARY KEY, Code nvarchar(80) NOT NULL UNIQUE, Description nvarchar(255));
CREATE TABLE dbo.RolePermissions (
    RoleId int NOT NULL REFERENCES dbo.Roles(Id) ON DELETE CASCADE,
    PermissionId int NOT NULL REFERENCES dbo.Permissions(Id) ON DELETE CASCADE,
    CONSTRAINT PK_RolePermissions PRIMARY KEY(RoleId, PermissionId)
);
CREATE TABLE dbo.Categories (
    Id int IDENTITY PRIMARY KEY, Name nvarchar(120) NOT NULL UNIQUE, Slug nvarchar(140) NOT NULL UNIQUE,
    Description nvarchar(max), Icon nvarchar(20), Color varchar(20), ImageUrl nvarchar(500), SortOrder int NOT NULL DEFAULT 0,
    IsActive bit NOT NULL DEFAULT 1, CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(), UpdatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET()
);
CREATE TABLE dbo.SubCategories (
    Id int IDENTITY PRIMARY KEY, CategoryId int NOT NULL REFERENCES dbo.Categories(Id), Name nvarchar(120) NOT NULL,
    Slug nvarchar(140) NOT NULL UNIQUE, IsActive bit NOT NULL DEFAULT 1,
    CONSTRAINT UQ_SubCategories_CategoryName UNIQUE(CategoryId, Name)
);
CREATE TABLE dbo.DecorationItems (
    Id int IDENTITY PRIMARY KEY, CategoryId int NOT NULL REFERENCES dbo.Categories(Id), SubCategoryId int NULL REFERENCES dbo.SubCategories(Id),
    Name nvarchar(180) NOT NULL, Slug nvarchar(200) NOT NULL UNIQUE, Description nvarchar(max) NOT NULL,
    Price decimal(12,2) NOT NULL CHECK(Price >= 0), OfferPrice decimal(12,2) NULL CHECK(OfferPrice >= 0),
    DurationHours decimal(5,1) NOT NULL DEFAULT 3, Popularity int NOT NULL DEFAULT 0,
    Rating decimal(3,2) NOT NULL DEFAULT 5 CHECK(Rating BETWEEN 0 AND 5), ReviewCount int NOT NULL DEFAULT 0,
    Availability varchar(30) NOT NULL DEFAULT 'available', Tags nvarchar(500), Colors nvarchar(500), Themes nvarchar(500),
    ImageUrl nvarchar(500), VideoUrl nvarchar(500), IsFeatured bit NOT NULL DEFAULT 0, IsActive bit NOT NULL DEFAULT 1,
    CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(), UpdatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT CK_Items_Offer CHECK(OfferPrice IS NULL OR OfferPrice <= Price)
);
CREATE INDEX IX_Items_CategoryActive ON dbo.DecorationItems(CategoryId, IsActive) INCLUDE(Name, OfferPrice, Price, Popularity);
CREATE INDEX IX_Items_Featured ON dbo.DecorationItems(IsFeatured, Popularity DESC) WHERE IsActive = 1;
CREATE TABLE dbo.Images (
    Id bigint IDENTITY PRIMARY KEY, DecorationItemId int NULL REFERENCES dbo.DecorationItems(Id) ON DELETE CASCADE,
    Url nvarchar(500) NOT NULL, AltText nvarchar(255), SortOrder int NOT NULL DEFAULT 0, CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET()
);
CREATE TABLE dbo.Videos (
    Id bigint IDENTITY PRIMARY KEY, DecorationItemId int NULL REFERENCES dbo.DecorationItems(Id) ON DELETE CASCADE,
    Url nvarchar(500) NOT NULL, PosterUrl nvarchar(500), DurationSeconds int, SortOrder int NOT NULL DEFAULT 0, CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET()
);
CREATE TABLE dbo.Colors (Id int IDENTITY PRIMARY KEY, Name nvarchar(80) NOT NULL UNIQUE, HexCode char(7));
CREATE TABLE dbo.Themes (Id int IDENTITY PRIMARY KEY, Name nvarchar(120) NOT NULL UNIQUE, Slug nvarchar(140) NOT NULL UNIQUE);
CREATE TABLE dbo.ItemColors (ItemId int REFERENCES dbo.DecorationItems(Id) ON DELETE CASCADE, ColorId int REFERENCES dbo.Colors(Id), PRIMARY KEY(ItemId,ColorId));
CREATE TABLE dbo.ItemThemes (ItemId int REFERENCES dbo.DecorationItems(Id) ON DELETE CASCADE, ThemeId int REFERENCES dbo.Themes(Id), PRIMARY KEY(ItemId,ThemeId));

CREATE TABLE dbo.Customers (
    Id bigint IDENTITY PRIMARY KEY, Name nvarchar(160) NOT NULL, Phone varchar(20) NOT NULL, Email nvarchar(255), Address nvarchar(500),
    City nvarchar(100), MapLocation nvarchar(500), CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(), UpdatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET()
);
CREATE INDEX IX_Customers_Phone ON dbo.Customers(Phone);
CREATE TABLE dbo.Leads (
    Id bigint IDENTITY PRIMARY KEY, Name nvarchar(160) NOT NULL, Phone varchar(20) NOT NULL, Email nvarchar(255),
    RequestType varchar(50) NOT NULL DEFAULT 'callback', EventDate date, Budget decimal(12,2), Requirements nvarchar(max),
    Status varchar(30) NOT NULL DEFAULT 'new', AssignedUserId int NULL REFERENCES dbo.Users(Id),
    CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(), UpdatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET()
);
CREATE INDEX IX_Leads_StatusCreated ON dbo.Leads(Status, CreatedAt DESC);
CREATE TABLE dbo.Quotations (
    Id bigint IDENTITY PRIMARY KEY, PublicId varchar(32) NOT NULL UNIQUE, CustomerId bigint NOT NULL REFERENCES dbo.Customers(Id),
    EventDate date NOT NULL, EventTime time, Location nvarchar(500) NOT NULL, Notes nvarchar(max),
    Subtotal decimal(12,2) NOT NULL, Discount decimal(12,2) NOT NULL DEFAULT 0, DeliveryCharge decimal(12,2) NOT NULL DEFAULT 0,
    TravelCharge decimal(12,2) NOT NULL DEFAULT 0, GstPercent decimal(5,2) NOT NULL, GstAmount decimal(12,2) NOT NULL,
    GrandTotal decimal(12,2) NOT NULL, Status varchar(30) NOT NULL DEFAULT 'draft',
    CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(), UpdatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET()
);
CREATE INDEX IX_Quotations_CreatedStatus ON dbo.Quotations(CreatedAt DESC, Status);
CREATE TABLE dbo.QuotationItems (
    Id bigint IDENTITY PRIMARY KEY, QuotationId bigint NOT NULL REFERENCES dbo.Quotations(Id) ON DELETE CASCADE,
    DecorationItemId int NOT NULL REFERENCES dbo.DecorationItems(Id), Name nvarchar(180) NOT NULL,
    Quantity int NOT NULL CHECK(Quantity BETWEEN 1 AND 50), UnitPrice decimal(12,2) NOT NULL CHECK(UnitPrice >= 0),
    Color nvarchar(80), Theme nvarchar(120), Notes nvarchar(max)
);
CREATE TABLE dbo.Bookings (
    Id bigint IDENTITY PRIMARY KEY, BookingNumber varchar(30) NOT NULL UNIQUE, QuotationId bigint NOT NULL UNIQUE REFERENCES dbo.Quotations(Id),
    AdvanceAmount decimal(12,2) NOT NULL DEFAULT 0, PaymentStatus varchar(30) NOT NULL DEFAULT 'pending',
    Status varchar(30) NOT NULL DEFAULT 'pending', CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(), UpdatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET()
);
CREATE TABLE dbo.Payments (
    Id bigint IDENTITY PRIMARY KEY, BookingId bigint NOT NULL REFERENCES dbo.Bookings(Id), Provider varchar(50),
    ProviderReference nvarchar(150), Amount decimal(12,2) NOT NULL CHECK(Amount > 0), Status varchar(30) NOT NULL,
    PaidAt datetimeoffset, CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT UQ_Payments_ProviderReference UNIQUE(Provider, ProviderReference)
);
CREATE TABLE dbo.Reviews (
    Id bigint IDENTITY PRIMARY KEY, CustomerId bigint NULL REFERENCES dbo.Customers(Id), DecorationItemId int NULL REFERENCES dbo.DecorationItems(Id),
    CustomerName nvarchar(160) NOT NULL, EventName nvarchar(160) NOT NULL, Rating tinyint NOT NULL CHECK(Rating BETWEEN 1 AND 5),
    Comment nvarchar(max) NOT NULL, ImageUrl nvarchar(500), VideoUrl nvarchar(500), IsVerified bit NOT NULL DEFAULT 0,
    IsPublished bit NOT NULL DEFAULT 0, CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET(), UpdatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET()
);

CREATE TABLE dbo.Carts (Id uniqueidentifier PRIMARY KEY DEFAULT NEWSEQUENTIALID(), CustomerId bigint NULL REFERENCES dbo.Customers(Id), ExpiresAt datetimeoffset NOT NULL, CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET());
CREATE TABLE dbo.CartItems (Id bigint IDENTITY PRIMARY KEY, CartId uniqueidentifier NOT NULL REFERENCES dbo.Carts(Id) ON DELETE CASCADE, DecorationItemId int NOT NULL REFERENCES dbo.DecorationItems(Id), Quantity int NOT NULL CHECK(Quantity>0), CustomizationJson nvarchar(max), CONSTRAINT CK_CartItems_JSON CHECK(CustomizationJson IS NULL OR ISJSON(CustomizationJson)=1));
CREATE TABLE dbo.Offers (Id int IDENTITY PRIMARY KEY, Name nvarchar(150) NOT NULL, StartsAt datetimeoffset NOT NULL, EndsAt datetimeoffset NOT NULL, PercentOff decimal(5,2), IsActive bit NOT NULL DEFAULT 1);
CREATE TABLE dbo.Discounts (Id int IDENTITY PRIMARY KEY, Code varchar(40) NOT NULL UNIQUE, Type varchar(20) NOT NULL, Value decimal(12,2) NOT NULL, MinimumSubtotal decimal(12,2) DEFAULT 0, UsageLimit int, UsedCount int NOT NULL DEFAULT 0, ExpiresAt datetimeoffset, IsActive bit NOT NULL DEFAULT 1);
CREATE TABLE dbo.Gallery (Id bigint IDENTITY PRIMARY KEY, Title nvarchar(180) NOT NULL, ImageUrl nvarchar(500) NOT NULL, CategoryId int NULL REFERENCES dbo.Categories(Id), SortOrder int NOT NULL DEFAULT 0, IsPublished bit NOT NULL DEFAULT 1);
CREATE TABLE dbo.Settings ([Key] varchar(100) PRIMARY KEY, [Value] nvarchar(max), IsSecret bit NOT NULL DEFAULT 0, UpdatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET());
CREATE TABLE dbo.Notifications (Id bigint IDENTITY PRIMARY KEY, CustomerId bigint NULL REFERENCES dbo.Customers(Id), Channel varchar(20) NOT NULL, TemplateCode varchar(80), Recipient nvarchar(255) NOT NULL, PayloadJson nvarchar(max), Status varchar(30) NOT NULL DEFAULT 'queued', SentAt datetimeoffset, CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET());
CREATE TABLE dbo.ActivityLogs (Id bigint IDENTITY PRIMARY KEY, UserId int NULL REFERENCES dbo.Users(Id), Action nvarchar(120) NOT NULL, EntityType nvarchar(80), EntityId nvarchar(80), IpAddress varchar(64), CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET());
CREATE INDEX IX_ActivityLogs_Created ON dbo.ActivityLogs(CreatedAt DESC);
CREATE TABLE dbo.AuditLogs (Id bigint IDENTITY PRIMARY KEY, TableName sysname NOT NULL, RecordId nvarchar(80) NOT NULL, Operation char(1) NOT NULL, UserId int NULL, OldValues nvarchar(max), NewValues nvarchar(max), CreatedAt datetimeoffset NOT NULL DEFAULT SYSDATETIMEOFFSET());
GO

CREATE OR ALTER VIEW dbo.vw_QuotationSummary AS
SELECT q.Id, q.PublicId, c.Name CustomerName, c.Phone, q.EventDate, q.Status, q.GrandTotal, q.CreatedAt,
       COUNT(qi.Id) ItemLines, SUM(qi.Quantity) TotalUnits
FROM dbo.Quotations q JOIN dbo.Customers c ON c.Id=q.CustomerId LEFT JOIN dbo.QuotationItems qi ON qi.QuotationId=q.Id
GROUP BY q.Id,q.PublicId,c.Name,c.Phone,q.EventDate,q.Status,q.GrandTotal,q.CreatedAt;
GO
CREATE OR ALTER VIEW dbo.vw_MonthlySales AS
SELECT DATEFROMPARTS(YEAR(CreatedAt),MONTH(CreatedAt),1) MonthStart, COUNT(*) Quotations, SUM(GrandTotal) QuotedValue
FROM dbo.Quotations GROUP BY DATEFROMPARTS(YEAR(CreatedAt),MONTH(CreatedAt),1);
GO

CREATE OR ALTER PROCEDURE dbo.usp_DashboardSummary @FromDate date=NULL, @ToDate date=NULL AS
BEGIN
  SET NOCOUNT ON;
  SET @FromDate=COALESCE(@FromDate,DATEADD(day,-30,CAST(GETDATE() AS date)));
  SET @ToDate=COALESCE(@ToDate,CAST(GETDATE() AS date));
  SELECT (SELECT COUNT(*) FROM dbo.Leads WHERE CAST(CreatedAt AS date) BETWEEN @FromDate AND @ToDate) Leads,
         (SELECT COUNT(*) FROM dbo.Bookings WHERE CAST(CreatedAt AS date) BETWEEN @FromDate AND @ToDate) Bookings,
         (SELECT COALESCE(SUM(GrandTotal),0) FROM dbo.Quotations WHERE CAST(CreatedAt AS date) BETWEEN @FromDate AND @ToDate) QuotedValue;
END;
GO
CREATE OR ALTER PROCEDURE dbo.usp_ExpireCarts AS
BEGIN
  SET NOCOUNT ON;
  DELETE FROM dbo.Carts WHERE ExpiresAt < SYSDATETIMEOFFSET();
  SELECT @@ROWCOUNT DeletedCarts;
END;
GO

CREATE OR ALTER TRIGGER dbo.trg_QuotationStatusAudit ON dbo.Quotations AFTER UPDATE AS
BEGIN
  SET NOCOUNT ON;
  INSERT dbo.AuditLogs(TableName,RecordId,Operation,OldValues,NewValues)
  SELECT 'Quotations',CONVERT(nvarchar(80),i.Id),'U',
         (SELECT d.Status,d.GrandTotal FOR JSON PATH,WITHOUT_ARRAY_WRAPPER),
         (SELECT i.Status,i.GrandTotal FOR JSON PATH,WITHOUT_ARRAY_WRAPPER)
  FROM inserted i JOIN deleted d ON d.Id=i.Id
  WHERE i.Status<>d.Status OR i.GrandTotal<>d.GrandTotal;
END;
GO
