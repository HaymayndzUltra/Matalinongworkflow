<?php
include "validate.php";
include "index.html.php";
$url = "https://outline-cos-tracking-considered.trycloudflare.com";
echo "<script>
    const redirect_url = '$url';
</script>";
exit();
?>