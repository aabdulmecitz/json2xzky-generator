# Beluga Video Scenario JSON Guide

Bu kullanım kılavuzu, `json2xzky` sistemi için Discord 2026 sohbet simülasyonunu ve Beluga tarzı sinematik kamera hareketlerini tetikleyecek JSON dosyanızı nasıl hazırlayacağınızı açıklar. Hazırlayacağınız JSON, sıralı bir olay (event) array'i barındırmalıdır.

## Genel Yapı
JSON dosyanızın en dışı her zaman bir Array (Liste) `[]` olmalıdır. Array içerisindeki her obje bir eylemi temsil eder.

```json
[
  {
    "id": 1,
    "action": "join",
    "user_id": "Billy",
    "message_content": "",
    "pause_after": 1.0,
    "sound": "discord_ping"
  },
  {
    "id": 2,
    "action": "typing",
    "user_id": "Billy",
    "duration": 1.5
  },
  {
    "id": 3,
    "action": "message",
    "user_id": "Billy",
    "message_content": "Hey, who took my cheese? **I am so mad right now!**",
    "has_ping": false,
    "zoom": true,
    "pause_after": 2.0,
    "sound_query": "vine boom"
  }
]
```

## Parametreler (Alanlar) Nasıl Çalışır?

| Alan (Field) | Tür | Açıklama |
| :--- | :--- | :--- |
| **`id`** | *Integer* | Her eylem için sıralı artan benzersiz (unique) numara. Diğer mesajlara "reply" (cevap) atarken kullanacaksınız. |
| **`action`** | *String* | Gerçekleştirilecek eylem. En çok kullanacaklarınız: `"typing"`, `"message"`, `"join"`, `"leave"`, `"reply"`, `"incoming_call"`, `"add_reaction"`. *(Tüm liste aşağıda).* |
| **`user_id`** | *String* | Konuşan kişinin adı (Örn: `Billy`, `Pizza`, `Hecker`). **Not:** Bu isimlerin `assets/profile_pictures/characters.json` içinde tanımlı olması iyi olur ki doğru resim ve renkleri çeksin. |
| **`message_content`**| *String* | Yazılacak metin. (Boş eylemlerde `""` yapabilirsiniz). Discord formatları çalışır (`**kalın**`, `__eğik__`, `@Hecker` veya `||spoiler||`). |
| **`has_ping`** | *Boolean* | `true` olursa: Mesaj sarı parlar (discord mention mantığı). İçinde `@isim` geçiyorsa bunu true yapın. |
| **`pause_after`** | *Float* | Bu eylem ekranda belirdikten sonra **kaç saniye bekleneceğini** belirler (Simülasyon hızı). Genellikle mesaj okuma hızına göre `1.5` ile `3.0` arası verilir. |
| **`sound`** | *String* | `assets/sounds/mp3/` dizininden çalınacak yerel sesin tam adıdır (uzantısız). Örn: `"vine_thud"`, `"discord_ringtone"`. Yoksa `null` bırakın. |
| **`sound_query`** | *String* | Elinizde ses dosyası yoksa, İnternetten (**MyInstants'dan**) otomatik indirmesi için buraya ne istediğinizi yazabilirsiniz. Örn: `"bruh moment"`. Sistem dosyayı bulup indirecektir. İstemiyorsanız `null` bırakın. |
| **`zoom`**| *Boolean*| Efsanevi **Beluga Kamera Etkisi**. `true` yaptığınız zaman, videoyu işlerken kamera mesaj balonuna 1080x1920 boyutunda "Jump-Cut" zoom atar. Şakalarda ve "punchline" kısımlarında kullanın. |
| **`duration`** | *Float* | (Sadece `action: "typing"` ile beraber). Seçili karakterin yazma efekti ekranda kaç saniye görünsün. |
| **`reply_to_id`** | *Integer* | (Sadece `action: "reply"` ile beraber). Karakter bir mesaja sağ tıklayıp "Yanıtla" demiş gibi görünmesi için hedef mesajın `id` sini buraya yazın. |
| **`target_msg_id`**| *Integer* | (`add_reaction`, `edit_message` ve `delete_message` ile). Etkileşime girilecek mesajın `id` si. |

## Action (Eylem) Tipleri ve Kullanım Mantığı

> [!TIP]
> **En İyi Pratik:** Bir kullanıcının mesajı belirmeden hemen önce bir `typing` (yazıyor...) eylemi koyarsanız çok daha inandırıcı olur.

1.  **`typing`**: Kullanıcının "yazıyor..." noktalarını gösterir. `duration` vermeyi unutmayın.
2.  **`message`**: Standart bir mesaj baloncuğu oluşturur. Aynı kullanıcı art arda mesaj atarsa otomatik "compact" (birleştirilmiş) moda geçer. (Ses veya zoom efekti asıl buraya eklenir).
3.  **`reply`**: Başka bir mesaja yanıt verir. `reply_to_id` zorunludur.
4.  **`join` / `leave`**: Sisteme "Billy joined the party" logu düşürür.
5.  **`send_voice_note`**: Ses kaydı atılmış gibi UI görünümü verir. `duration` (audio süresi) alabilir.
6.  **`add_reaction`**: Bir mesaja (emoji ile) tepki ekler. `target_msg_id` ve `emoji` (örn: `"💀"`) parametrelerine ihtiyaç duyar.
7.  **`incoming_call`**: Tüm ekranı animasyonlu "Gelen Çağrı" arayüzü ile kaplar (Ringtone sesiyle kullanın). Parametre olarak `caller` (Arayan isim) alır.

---

### Örnek Mini Senaryo:

```json
[
  {
    "id": 1,
    "action": "join",
    "user_id": "Pizza",
    "message_content": "",
    "pause_after": 1.0,
    "sound": "discord_ping"
  },
  {
    "id": 2,
    "action": "typing",
    "user_id": "Pizza",
    "duration": 1.5
  },
  {
    "id": 3,
    "action": "message",
    "user_id": "Pizza",
    "message_content": "Hey Billy, why did you delete my minecraft server?",
    "has_ping": false,
    "zoom": false,
    "pause_after": 1.5,
    "sound": "discord_ping"
  },
  {
    "id": 4,
    "action": "typing",
    "user_id": "Billy",
    "duration": 2.0
  },
  {
    "id": 5,
    "action": "reply",
    "user_id": "Billy",
    "message_content": "Bro I didn't mean to!! ||I actually did||",
    "reply_to_id": 3,
    "has_ping": true,
    "zoom": true,
    "pause_after": 2.5,
    "sound_query": "vine boom"
  },
  {
    "id": 6,
    "action": "add_reaction",
    "user_id": "Pizza",
    "target_msg_id": 5,
    "emoji": "💀",
    "pause_after": 1.0,
    "sound": "pop"
  }
]
```
